"""Update Stock is controlled from Chundakadan Settings, not by the user."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events import stock_control as sc
from chundakadan.doc_events.purchase_invoice import apply_stock_defaults as pi_defaults
from chundakadan.doc_events.sales_invoice import COMPANY_STORE_WAREHOUSE, auto_create_delivery_note
from chundakadan.doc_events.sales_invoice import apply_stock_defaults as si_defaults
from chundakadan.testing import a_company, a_warehouse

test_ignore = ["Sales Invoice", "Purchase Invoice", "Customer", "Supplier", "Company", "User"]


class TestUpdateStockControl(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls._commit = frappe.db.commit
		frappe.db.commit = lambda *a, **k: None  # keep the setup inside this transaction
		sc.ensure_update_stock_settings()
		cls.item = frappe.db.get_value("Item", {"is_stock_item": 1}, "name", order_by="name asc")
		cls.company = a_company()
		cls.warehouse = a_warehouse(cls.company) if cls.company else None

	@classmethod
	def tearDownClass(cls):
		frappe.db.commit = cls._commit
		super().tearDownClass()

	def setUp(self):
		if not self.company or not self.warehouse:
			self.skipTest("this bench has no company with a warehouse")
		# Both hooks bail out unless the company is in this map, so on any
		# bench but the live one they never ran and the tests passed on the
		# value the "user" had set. Point the map at this bench's company.
		patcher = patch.dict(COMPANY_STORE_WAREHOUSE, {self.company: self.warehouse})
		patcher.start()
		self.addCleanup(patcher.stop)

	def _set(self, doctype, value):
		frappe.db.set_single_value(sc.SETTINGS, sc.UPDATE_STOCK_SETTINGS[doctype][0], value)

	def _invoice(self, doctype, **kw):
		doc = frappe.new_doc(doctype)
		doc.company = self.company
		doc.update(kw)
		doc.append("items", {"item_code": self.item})
		return doc

	def test_settings_fields_exist(self):
		meta = frappe.get_meta(sc.SETTINGS)
		for _doctype, (fieldname, _label, _default) in sc.UPDATE_STOCK_SETTINGS.items():
			self.assertTrue(meta.get_field(fieldname), f"{fieldname} missing")

	def test_a_setting_nobody_saved_reads_as_its_default(self):
		"""Not what this site happens to have: a site where somebody turned the
		toggle on is a site where asserting the shipped default would fail."""
		for doctype, (fieldname, _label, default) in sc.UPDATE_STOCK_SETTINGS.items():
			frappe.db.delete("Singles", {"doctype": sc.SETTINGS, "field": fieldname})
			frappe.clear_document_cache(sc.SETTINGS, sc.SETTINGS)
			self.assertEqual(sc.get_update_stock(doctype), default, f"{fieldname} ignored its default")

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

	def test_no_delivery_note_when_invoice_updates_stock(self):
		invoice = frappe.db.get_value(
			"Sales Invoice",
			{"company": self.company, "docstatus": 1, "update_stock": 1, "is_return": 0},
			"name",
		)
		if not invoice:
			self.skipTest("no submitted invoice with update_stock=1")
		doc = frappe.get_doc("Sales Invoice", invoice)
		auto_create_delivery_note(doc)
		self.assertFalse(
			frappe.db.exists("Delivery Note Item", {"against_sales_invoice": doc.name, "docstatus": ["<", 2]})
		)

	def test_defaults_are_seeded_when_the_toggles_are_created(self):
		# simulate a site that never had the toggles
		for _doctype, (fieldname, _label, _default) in sc.UPDATE_STOCK_SETTINGS.items():
			frappe.db.delete("Custom Field", {"name": f"{sc.SETTINGS}-{fieldname}"})
			frappe.db.delete("Singles", {"doctype": sc.SETTINGS, "field": fieldname})
		frappe.clear_cache(doctype=sc.SETTINGS)

		sc.ensure_update_stock_settings()

		self.assertEqual(sc.get_update_stock("Sales Invoice"), 0)
		self.assertEqual(sc.get_update_stock("Purchase Invoice"), 1)

	def test_an_existing_choice_is_never_overwritten(self):
		self._set("Purchase Invoice", 0)
		sc.ensure_update_stock_settings()
		self.assertEqual(sc.get_update_stock("Purchase Invoice"), 0)
