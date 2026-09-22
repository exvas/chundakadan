import frappe

from chundakadan.seed.role_profiles import PROFILES, _ensure_module_profile


def execute():
	"""Re-sync the CDN GM Module Profile so the GM sees every module.

	`apply_cdn_gm_full_access` ran on 2026-09-15 before the profile was
	widened, and patches only run once, so CDN GM kept 29 blocked modules —
	which is why the GM could not see the Tracks workspace (module Field
	Sales). Users carrying the profile are refreshed too, since a user's
	block_modules are a copy made when the user is saved.
	"""
	if not frappe.db.exists("Module Profile", "CDN GM"):
		return

	profile = next(p for p in PROFILES if p["name"] == "CDN GM")
	_ensure_module_profile(profile, overwrite=True)

	for user in frappe.get_all("User", filters={"module_profile": "CDN GM"}, pluck="name"):
		doc = frappe.get_doc("User", user)
		doc.flags.ignore_permissions = True
		doc.save()
