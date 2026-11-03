"""Installing this app must not need ERPNext's setup wizard to have run."""

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.seed.customer_groups import GROUPS, ROOT, ensure_customer_groups


class TestCustomerGroupSeed(FrappeTestCase):
	def test_the_groups_exist_after_seeding(self):
		if not frappe.db.exists("Customer Group", ROOT):
			self.skipTest("this site has no customer group tree")
		ensure_customer_groups()
		for name in GROUPS:
			self.assertTrue(frappe.db.exists("Customer Group", name), name)

	def test_running_it_twice_changes_nothing(self):
		if not frappe.db.exists("Customer Group", ROOT):
			self.skipTest("this site has no customer group tree")
		ensure_customer_groups()
		before = frappe.db.get_value("Customer Group", GROUPS[0], "modified")
		ensure_customer_groups()
		self.assertEqual(frappe.db.get_value("Customer Group", GROUPS[0], "modified"), before)

	def test_a_site_without_the_root_creates_nothing(self):
		"""The whole point. Without the root there is no tree to hang them on,
		and attempting the insert is what died unpacking None mid-install.

		Asserted by counting inserts, not by "it did not raise": the seed
		catches its own errors, so a missing guard would look the same."""
		attempted = []
		original_exists, original_get_doc = frappe.db.exists, frappe.get_doc

		def nothing_exists(doctype, name=None, *args, **kwargs):
			if doctype == "Customer Group":
				return None
			return original_exists(doctype, name, *args, **kwargs)

		def record(*args, **kwargs):
			attempted.append(args[0] if args else kwargs)
			raise AssertionError("must not insert without the root")

		frappe.db.exists, frappe.get_doc = nothing_exists, record
		try:
			ensure_customer_groups()
		finally:
			frappe.db.exists, frappe.get_doc = original_exists, original_get_doc

		self.assertEqual(attempted, [], "tried to create a group with no parent to put it under")

	def test_the_fixture_is_gone(self):
		"""It is what broke the install; it must not come back."""
		fixtures = frappe.get_hooks("fixtures", app_name="chundakadan")
		named = [f.get("doctype") for f in fixtures if isinstance(f, dict)]
		self.assertNotIn("Customer Group", named)
