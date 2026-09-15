import frappe

from chundakadan.seed.role_profiles import PROFILES, _ensure_module_profile, _ensure_role_profile


def execute():
	"""Apply the widened CDN GM profile (commit 5f3b696) once.

	seed_profiles no longer overwrites existing profiles, so this one-time
	patch carries that change to sites where CDN GM already exists. After it
	runs, the profile can be edited from the UI.
	"""
	profile = next(p for p in PROFILES if p["name"] == "CDN GM")
	if not frappe.db.exists("Role Profile", profile["name"]):
		return
	_ensure_role_profile(profile, overwrite=True)
	_ensure_module_profile(profile, overwrite=True)
