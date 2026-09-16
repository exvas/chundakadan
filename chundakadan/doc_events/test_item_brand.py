import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events.item_brand import ensure_item_brand_mandatory

test_ignore = ["Item", "Brand"]


class TestItemBrandMandatory(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls._commit = frappe.db.commit
		frappe.db.commit = lambda *a, **k: None

	@classmethod
	def tearDownClass(cls):
		frappe.db.commit = cls._commit
		super().tearDownClass()

	def test_brand_becomes_mandatory(self):
		ensure_item_brand_mandatory()
		self.assertTrue(frappe.get_meta("Item", cached=False).get_field("brand").reqd)

	def test_saving_an_item_without_brand_is_refused(self):
		ensure_item_brand_mandatory()
		frappe.clear_cache(doctype="Item")
		item = frappe.get_doc("Item", frappe.db.get_value("Item", {"disabled": 0}, "name"))
		item.brand = None
		with self.assertRaises(frappe.MandatoryError):
			item.save()

	def test_is_idempotent(self):
		ensure_item_brand_mandatory()
		ensure_item_brand_mandatory()
		self.assertEqual(
			frappe.db.count("Property Setter", {"doc_type": "Item", "field_name": "brand", "property": "reqd"}), 1
		)
