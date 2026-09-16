"""Update Stock is controlled from Chundakadan Settings, not by the user."""

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events import stock_control as sc
from chundakadan.doc_events.purchase_invoice import apply_stock_defaults as pi_defaults
from chundakadan.doc_events.sales_invoice import apply_stock_defaults as si_defaults
from chundakadan.doc_events.sales_invoice import auto_create_delivery_note

test_ignore = ["Sales Invoice", "Purchase Invoice", "Customer", "Supplier", "Company", "User"]
COMPANY = "Chundakadan Agencies"


class TestUpdateStockControl(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls._commit = frappe.db.commit
		frappe.db.commit = lambda *a, **k: None  # keep the setup inside this transaction
		sc.ensure_update_stock_settings()
		cls.item = frappe.db.get_value("Item", {"is_stock_item": 1}, "name")

	@classmethod
	def tearDownClass(cls):
		frappe.db.commit = cls._commit
		super().tearDownClass()

	def _set(self, doctype, value):
		frappe.db.set_single_value(sc.SETTINGS, sc.UPDATE_STOCK_SETTINGS[doctype][0], value)

	def _invoice(self, doctype, **kw):
		doc = frappe.new_doc(doctype)
		doc.company = COMPANY
		doc.update(kw)
		doc.append("items", {"item_code": self.item})
		return doc

	def test_settings_fields_exist_with_defaults(self):
		meta = frappe.get_meta(sc.SETTINGS)
		for doctype, (fieldname, _label, default) in sc.UPDATE_STOCK_SETTINGS.items():
			self.assertTrue(meta.get_field(fieldname), f"{fieldname} missing")
			self.assertEqual(sc.get_update_stock(doctype), default)

	def test_update_stock_is_read_only_on_both_doctypes(self):
		for doctype in sc.UPDATE_STOCK_SETTINGS:
			self.assertTrue(
				frappe.get_meta(doctype).get_field("update_stock").read_only,
				f"{doctype}.update_stock should be read-only",
			)

	def test_sales_invoice_follows_the_setting(self):
		for value in (1, 0):
			self._set("Sales Invoice", value)
			doc = self._invoice("Sales Invoice", update_stock=1 - value)  # user tries the opposite
			si_defaults(doc)
			self.assertEqual(doc.update_stock, value)

	def test_purchase_invoice_follows_the_setting(self):
		for value in (0, 1):
			self._set("Purchase Invoice", value)
			doc = self._invoice("Purchase Invoice", update_stock=1 - value)
			pi_defaults(doc)
			self.assertEqual(doc.update_stock, value)

	def test_unsaved_setting_falls_back_to_default(self):
		frappe.db.delete("Singles", {"doctype": sc.SETTINGS, "field": "si_update_stock"})
		frappe.clear_document_cache(sc.SETTINGS, sc.SETTINGS)
		self.assertEqual(sc.get_update_stock("Sales Invoice"), 0)

	def test_no_delivery_note_when_invoice_updates_stock(self):
		invoice = frappe.db.get_value(
			"Sales Invoice",
			{"company": COMPANY, "docstatus": 1, "update_stock": 1, "is_return": 0},
			"name",
		)
		if not invoice:
			self.skipTest("no submitted invoice with update_stock=1")
		doc = frappe.get_doc("Sales Invoice", invoice)
		auto_create_delivery_note(doc)
		self.assertFalse(
			frappe.db.exists("Delivery Note Item", {"against_sales_invoice": doc.name, "docstatus": ["<", 2]})
		)
