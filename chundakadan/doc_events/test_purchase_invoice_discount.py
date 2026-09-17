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
		self.assertEqual(meta.get_field("discount_percentage").label, "Disc %")
		self.assertEqual(meta.get_field("discount_amount").label, "Disc Amnt")

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

	# qty (pcs), list price, discount %, discount amount, rate, amount — CAPRI DISCOUNT.xlsx
	SHEET = [
		(48000, 0.85, 57, 0.4845, 0.3655, 17544.00),
		(31200, 1.64, 57, 0.9348, 0.7052, 22002.24),
		(15600, 2.29, 57, 1.3053, 0.9847, 15361.32),
		(108000, 1.78, 54, 0.9612, 0.8188, 88430.40),
		(10200, 0.789, 22, 0.17358, 0.61542, 6277.28),
		(8400, 0.948, 22, 0.20856, 0.73944, 6211.30),
	]

	def _sheet_invoice(self):
		from erpnext.controllers.taxes_and_totals import calculate_taxes_and_totals

		pi = frappe.new_doc("Purchase Invoice")
		pi.company = frappe.db.get_value("Company", {}, "name")
		pi.currency = frappe.get_cached_value("Company", pi.company, "default_currency")
		pi.conversion_rate = 1
		for qty, list_price, pct, *_ in self.SHEET:
			pi.append("items", {"item_code": "_x", "qty": qty, "price_list_rate": list_price, "discount_percentage": pct, "rate": 0, "conversion_factor": 1})
		calculate_taxes_and_totals(pi)
		return pi

	def test_matches_discount_sheet(self):
		ensure_purchase_invoice_discount_columns()
		frappe.clear_cache(doctype="Purchase Invoice")
		pi = self._sheet_invoice()
		for row, (qty, list_price, pct, disc, rate, amount) in zip(pi.items, self.SHEET):
			self.assertAlmostEqual(row.discount_amount, disc, places=5, msg=qty)
			self.assertAlmostEqual(row.rate, rate, places=5, msg=qty)
			self.assertAlmostEqual(row.amount, amount, places=2, msg=qty)
		self.assertAlmostEqual(pi.total, 155826.54, places=2)

	def test_amount_precision_unchanged(self):
		ensure_purchase_invoice_discount_columns()
		frappe.clear_cache(doctype="Purchase Invoice")
		meta = frappe.get_meta(DOCTYPE)
		self.assertEqual(meta.get_field("rate").precision, "5")
		self.assertFalse(meta.get_field("amount").precision)
		self.assertFalse(meta.get_field("net_amount").precision)

