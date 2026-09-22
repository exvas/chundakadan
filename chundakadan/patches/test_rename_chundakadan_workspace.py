import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.patches.rename_chundakadan_workspace import NEW, OLD, execute


class TestRenameChundakadanWorkspace(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def _make(self, name):
		doc = frappe.get_doc({
			"doctype": "Workspace", "name": name, "title": name, "label": name,
			"module": "Chundakadan", "public": 1, "content": "[]", "sequence_id": 1.0,
		})
		doc.flags.name_set = True
		doc.flags.ignore_links = True
		doc.insert(ignore_permissions=True)
		return doc

	def test_renames_and_relabels(self):
		if frappe.db.exists("Workspace", NEW):
			frappe.delete_doc("Workspace", NEW, force=True)
		if not frappe.db.exists("Workspace", OLD):
			self._make(OLD)
		execute()
		self.assertFalse(frappe.db.exists("Workspace", OLD))
		self.assertEqual(frappe.db.get_value("Workspace", NEW, ["title", "label"], as_dict=True), frappe._dict({"title": NEW, "label": NEW}))

	def test_what_the_site_added_travels_with_it(self):
		if frappe.db.exists("Workspace", NEW):
			frappe.delete_doc("Workspace", NEW, force=True)
		if frappe.db.exists("Workspace", OLD):
			frappe.delete_doc("Workspace", OLD, force=True)
		doc = self._make(OLD)
		doc.append("roles", {"role": "Accounts Manager"})
		doc.icon = "star"
		doc.save()
		execute()
		moved = frappe.get_doc("Workspace", NEW)
		self.assertEqual([r.role for r in moved.roles], ["Accounts Manager"])
		self.assertEqual(moved.icon, "star")

	def test_running_twice_is_harmless(self):
		execute()
		execute()
		self.assertTrue(frappe.db.exists("Workspace", NEW))
		self.assertFalse(frappe.db.exists("Workspace", OLD))

	def test_both_present_keeps_the_new_one(self):
		if not frappe.db.exists("Workspace", NEW):
			self._make(NEW)
		if not frappe.db.exists("Workspace", OLD):
			self._make(OLD)
		execute()
		self.assertTrue(frappe.db.exists("Workspace", NEW))
		self.assertFalse(frappe.db.exists("Workspace", OLD))
