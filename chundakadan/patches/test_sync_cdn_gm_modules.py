import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.patches.sync_cdn_gm_modules import execute
from chundakadan.seed.role_profiles import PROFILES, _ensure_module_profile


class TestSyncCDNGMModules(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.profile = next(p for p in PROFILES if p["name"] == "CDN GM")
		_ensure_module_profile(self.profile, overwrite=False)
		if not frappe.db.exists("Module Profile", "CDN GM"):
			self.skipTest("CDN GM module profile missing")

	def tearDown(self):
		frappe.db.rollback()

	def test_gm_profile_blocks_nothing(self):
		doc = frappe.get_doc("Module Profile", "CDN GM")
		doc.append("block_modules", {"module": "Field Sales"})
		doc.save()
		self.assertTrue([b for b in frappe.get_doc("Module Profile", "CDN GM").block_modules])
		execute()
		self.assertEqual(frappe.get_doc("Module Profile", "CDN GM").block_modules, [])

	def test_users_on_the_profile_are_refreshed(self):
		user = frappe.db.get_value("User", {"module_profile": "CDN GM", "enabled": 1}, "name")
		if not user:
			self.skipTest("no user on the CDN GM module profile")
		doc = frappe.get_doc("User", user)
		doc.append("block_modules", {"module": "Field Sales"})
		doc.flags.ignore_permissions = True
		doc.save()
		execute()
		self.assertEqual(frappe.get_doc("User", user).block_modules, [])
