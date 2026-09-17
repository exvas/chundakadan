import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events.purchase_invoice_discount import DOCTYPE, PROPERTIES, ensure_purchase_invoice_discount_columns


class TestPurchaseInvoiceDiscountColumns(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()
		frappe.clear_cache(doctype="Purchase Invoice")

	def test_discount_fields_are_grid_columns(self):
		ensure_purchase_invoice_discount_columns()
		frappe.clear_cache(doctype="Purchase Invoice")
		meta = frappe.get_meta(DOCTYPE)
		for fieldname in ("price_list_rate", "discount_percentage", "discount_amount"):
			field = meta.get_field(fieldname)
			self.assertEqual(field.in_list_view, 1, fieldname)
		self.assertFalse(meta.get_field("discount_percentage").depends_on)
		self.assertFalse(meta.get_field("discount_amount").depends_on)
		self.assertEqual(meta.get_field("price_list_rate").label, "List Price")

	def test_grid_columns_fit(self):
		ensure_purchase_invoice_discount_columns()
		frappe.clear_cache(doctype="Purchase Invoice")
		meta = frappe.get_meta(DOCTYPE)
		listed = [f for f in meta.fields if f.in_list_view and not f.hidden]
		self.assertLessEqual(sum(f.columns or 1 for f in listed), 10, [(f.fieldname, f.columns) for f in listed])
		for fieldname in PROPERTIES:
			self.assertIn(fieldname, [f.fieldname for f in listed])

	def test_idempotent(self):
		ensure_purchase_invoice_discount_columns()
		ensure_purchase_invoice_discount_columns()
		count = frappe.db.count("Property Setter", {"doc_type": DOCTYPE, "field_name": "discount_percentage", "property": "in_list_view"})
		self.assertEqual(count, 1)

	def test_server_keeps_discount_values(self):
		pi = frappe.new_doc("Purchase Invoice")
		company = frappe.db.get_value("Company", {}, "name")
		pi.company = company
		pi.currency = frappe.get_cached_value("Company", company, "default_currency")
		pi.conversion_rate = 1
		pi.append("items", {"item_code": "_x", "qty": 240, "price_list_rate": 170, "discount_percentage": 57, "rate": 0, "conversion_factor": 1})
		from erpnext.controllers.taxes_and_totals import calculate_taxes_and_totals
		calculate_taxes_and_totals(pi)
		row = pi.items[0]
		self.assertAlmostEqual(row.rate, 73.10, places=2)
		self.assertAlmostEqual(row.discount_amount, 96.90, places=2)
		self.assertAlmostEqual(row.amount, 17544.00, places=2)
