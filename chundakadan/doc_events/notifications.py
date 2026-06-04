# Copyright (c) 2026, Chundakadan
# Doc-event hooks that fire mobile push notifications.

import frappe
from chundakadan.utils.push import send_to_all_employees


def hr_policy_updated(doc, method=None):
    """Fires on every HR Policy save. Sends a push to all Active
    employees telling them to re-fetch the policy. Mobile uses the
    `version` field to dedupe (it only re-downloads if the version
    advanced past what it has cached).

    Respects doc.notify_on_update — HR can uncheck it for cosmetic
    edits that don't warrant pinging the whole company.
    """
    if not getattr(doc, "notify_on_update", 1):
        return

    title = "HR Policy Updated"
    body = "Open the app to read the latest HR Policy."
    if (doc.policy_html or "").strip():
        # Tease a few words of the html as preview
        import re
        text = re.sub(r"<[^>]+>", " ", doc.policy_html).strip()
        if text:
            body = (text[:120] + "…") if len(text) > 120 else text

    try:
        send_to_all_employees(
            title=title,
            body=body,
            data={"route": "/hr_policy", "version": str(doc.version or 0)},
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "chundakadan.notifications.hr_policy_updated",
        )


def newsletter_sent(doc, method=None):
    """Fires after a Newsletter is inserted. Mobile shows it in the
    Newsletter list immediately; push tells the user it's there.

    Uses after_insert (not on_send) so it fires regardless of whether
    the Newsletter is also being emailed out.
    """
    title = f"New Newsletter: {doc.subject or 'Update'}"

    # Body — strip HTML, keep first ~120 chars as preview
    body = ""
    if doc.message:
        import re
        text = re.sub(r"<[^>]+>", " ", doc.message).strip()
        if text:
            body = (text[:120] + "…") if len(text) > 120 else text
    if not body:
        body = "Open the app to read."

    try:
        send_to_all_employees(
            title=title,
            body=body,
            data={"route": "/newsletter", "name": doc.name or ""},
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "chundakadan.notifications.newsletter_sent",
        )
