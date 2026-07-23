"""Self-heal corrupt cached sessions instead of hard-blocking the user.

Frappe's ``Session.get_session_data_from_cache()`` returns the cached inner
sessiondata as-is. If that dict is missing the ``user`` key (rare corruption:
a boot-path session rewrite racing a cache write), ``Session.resume()`` sets
``self.user = None`` and every subsequent request for that sid dies in
``validate_user()`` with the misleading::

    frappe.exceptions.ValidationError: User None is disabled.

The DB path (``get_session_data_from_db``) is immune because it patches
``data.user`` from the ``tabSessions.user`` column. So the fix is generic:
treat a corrupt cache entry as a cache miss — drop it and return ``None`` so
``get_session_data()`` falls through to the self-healing DB path (which also
re-primes the cache via ``_update_in_cache``). If the DB row is gone too, the
session expires normally to Guest and the user simply logs in again.

No user, sid, or site is special-cased anywhere.
"""

import frappe
from frappe.sessions import Session


def install():
	if getattr(Session.get_session_data_from_cache, "_cdn_session_heal", False):
		return  # already patched in this interpreter

	orig = Session.get_session_data_from_cache

	def get_session_data_from_cache(self):
		data = orig(self)
		if data is not None and not data.get("user"):
			# corrupt entry: without this it would resume as user=None and
			# throw "User None is disabled" on every request for this sid
			try:
				frappe.cache.hdel("session", self.sid)
				frappe.logger("chundakadan").warning(
					"session_healing: dropped corrupt cached session %s... (no user key); "
					"falling back to DB",
					str(self.sid)[:12],
				)
			except Exception:
				pass
			return None
		return data

	get_session_data_from_cache._cdn_session_heal = True
	Session.get_session_data_from_cache = get_session_data_from_cache


def clean_corrupt_sessions():
	"""Hourly scheduler backstop: sweep cached sessions missing the ``user`` key.

	Covers the theoretical worker that resumes sessions before anything imported
	this app (``HTTPRequest`` runs before the ``before_request`` hooks, and
	``get_hooks`` serves from the redis cache without importing app code).
	"""
	dropped = []
	for sid, data in (frappe.cache.hgetall("session") or {}).items():
		sid = sid if isinstance(sid, str) else sid.decode(errors="replace")
		if "user" not in (frappe._dict(data).get("data") or {}):
			frappe.cache.hdel("session", sid)
			dropped.append(sid[:12])
	if dropped:
		frappe.logger("chundakadan").warning(
			"session_healing: swept %d corrupt cached session(s): %s", len(dropped), dropped
		)
