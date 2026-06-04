# Copyright (c) 2026, Chundakadan
# Push-notification dispatch via Firebase Cloud Messaging.
#
# OPERATIONAL SETUP (one-time, by ops):
#   1. Install firebase-admin in the bench's venv:
#        bench pip install firebase-admin
#   2. Download the Firebase service account JSON from Firebase Console:
#        Project Settings → Service accounts → Generate new private key
#      (use the SAME Firebase project the mobile app talks to)
#   3. Place the JSON at /home/frappe/firebase-service-account.json
#      (or set `chundakadan_fcm_credentials_path` in site_config.json)
#   4. Restart the bench. send_to_users() will start working.
#
# If credentials are missing this module logs and returns silently
# instead of crashing — so the rest of the system (saves, hooks) works
# fine even before FCM is wired. Once credentials are in place, pushes
# start flowing without any code change.

import json
import os

import frappe
from frappe.utils import now

# Firebase Admin SDK app + initialised flag — module-level singleton so
# we only init once per worker.
_fcm_app = None
_fcm_init_attempted = False


def _ensure_fcm():
    """Initialise firebase_admin lazily. Returns True if ready, False if
    credentials are missing or firebase-admin isn't installed.
    """
    global _fcm_app, _fcm_init_attempted
    if _fcm_app is not None:
        return True
    if _fcm_init_attempted:
        # Already tried and failed — don't keep retrying within the same
        # worker, just no-op.
        return False
    _fcm_init_attempted = True

    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError:
        frappe.log_error(
            "firebase-admin not installed — push notifications disabled.\n"
            "Run: bench pip install firebase-admin",
            "chundakadan.push.import",
        )
        return False

    # Where's the service account JSON?
    cred_path = (
        frappe.conf.get("chundakadan_fcm_credentials_path")
        or "/home/frappe/firebase-service-account.json"
    )
    if not os.path.exists(cred_path):
        frappe.log_error(
            f"FCM service account JSON not found at {cred_path}. "
            "See chundakadan/utils/push.py header for setup instructions.",
            "chundakadan.push.credentials",
        )
        return False

    try:
        cred = credentials.Certificate(cred_path)
        _fcm_app = firebase_admin.initialize_app(cred, name="chundakadan")
        return True
    except ValueError:
        # initialize_app called twice with same name — grab existing
        try:
            _fcm_app = firebase_admin.get_app("chundakadan")
            return True
        except Exception:
            return False
    except Exception:
        frappe.log_error(frappe.get_traceback(), "chundakadan.push.init")
        return False


def _log_notification(user, title, body, data):
    """Create a persistent Notification Log row so the user can see this
    notification later from the mobile bell icon. Frappe's standard
    Notification Log doctype — used by the desk too.

    `data.route` + `data.name` get stored in document_type / document_name
    so the mobile can route to the right page when the user taps the
    log entry.
    """
    route = (data or {}).get("route", "")
    name = (data or {}).get("name", "")
    # Map route → doctype for the log row (so the desk dashboard also
    # makes sense if anyone clicks through)
    doctype_map = {
        "/hr_policy": "HR Policy",
        "/newsletter": "Newsletter",
    }
    doctype = doctype_map.get(route, "")
    try:
        log = frappe.get_doc({
            "doctype": "Notification Log",
            "subject": title,
            "for_user": user,
            "type": "Alert",
            "document_type": doctype,
            "document_name": name,
            "email_content": body,
            "from_user": "Administrator",
        })
        log.flags.ignore_permissions = True
        log.insert()
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "chundakadan.push._log_notification",
        )


def send_to_users(users, title, body, data=None):
    """Send a push notification to a list of users (each can have multiple
    FCM tokens — one per device). Invalid / stale tokens are pruned.
    Also writes a persistent Notification Log row per user so the
    mobile bell can show a history.

    Args:
        users: list of User name strings (emails)
        title: notification title
        body:  notification body
        data:  optional dict of extra data routed to the app (e.g.
               {"route": "/hr_policy", "version": "7"})

    Returns:
        dict {"sent": int, "failed": int, "skipped": int}
    """
    result = {"sent": 0, "failed": 0, "skipped": 0}
    if not users:
        return result

    # Persist a Notification Log row per user — independent of whether
    # FCM delivery succeeds. The bell icon reads this list.
    for u in users:
        _log_notification(u, title, body, data)
    frappe.db.commit()

    # Collect all tokens for these users
    tokens = frappe.get_all(
        "FCM Token",
        filters={"user": ["in", list(users)]},
        fields=["name", "token", "user"],
        ignore_permissions=True,
    )
    if not tokens:
        result["skipped"] = 1
        return result

    if not _ensure_fcm():
        # Credentials missing — log what WOULD have been sent so HR can
        # see the audit trail even before FCM is wired.
        for t in tokens:
            frappe.logger("chundakadan.push").info(
                f"[stub-send] user={t['user']} title={title!r} body={body!r}"
            )
        result["skipped"] = len(tokens)
        return result

    from firebase_admin import messaging

    stale_token_rows = []
    for t in tokens:
        try:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
                token=t["token"],
                android=messaging.AndroidConfig(priority="high"),
            )
            messaging.send(message, app=_fcm_app)
            result["sent"] += 1
        except messaging.UnregisteredError:
            # Token no longer valid — schedule for cleanup
            stale_token_rows.append(t["name"])
            result["failed"] += 1
        except Exception:
            frappe.log_error(frappe.get_traceback(), "chundakadan.push.send")
            result["failed"] += 1

    # Prune stale tokens so the same dead tokens don't waste cycles on
    # the next round of notifications
    if stale_token_rows:
        for n in stale_token_rows:
            try:
                frappe.delete_doc("FCM Token", n, ignore_permissions=True, force=True)
            except Exception:
                pass
        frappe.db.commit()

    return result


def send_to_all_employees(title, body, data=None):
    """Convenience wrapper — sends a push to every User linked to an
    Active Employee. Used by HR Policy / Newsletter hooks.
    """
    user_ids = frappe.db.sql_list(
        """
        SELECT DISTINCT user_id FROM `tabEmployee`
        WHERE status = 'Active'
          AND user_id IS NOT NULL
          AND user_id != ''
        """
    )
    return send_to_users(user_ids, title, body, data)
