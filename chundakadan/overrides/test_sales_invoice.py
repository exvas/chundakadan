"""A standalone credit note must cost its goods, not stop or guess."""

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.overrides.sales_invoice import (
	fallback_rate,
	hold_rows,
	is_standalone_return,
	release_rows,
)

PRICED = "_Test CDN Return Priced Item"
UNPRICED = "_Test CDN Return Unpriced Item"


def make_item(code, valuation_rate=0.0, standard_rate=0.0, is_stock_item=1):
	if frappe.db.exists("Item", code):
		frappe.db.set_value(
			"Item",
			code,
			{
				"valuation_rate": valuation_rate,
				"standard_rate": standard_rate,
				"is_stock_item": is_stock_item,
			},
		)
	else:
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": code,
				"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				"stock_uom": "Nos",
				"is_stock_item": is_stock_item,
				"valuation_rate": valuation_rate,
				"standard_rate": standard_rate,
				"gst_hsn_code": frappe.db.get_value("GST HSN Code", {}, "name"),
			}
		).insert(ignore_permissions=True)
	frappe.clear_cache(doctype="Item")
	return code


def row(item_code, **kwargs):
	return frappe._dict({"item_code": item_code, "qty": 1, "rate": 999, **kwargs})


def invoice(rows, **kwargs):
	doc = frappe._dict({"is_return": 1, "return_against": None, "update_stock": 1, "items": rows, **kwargs})
	doc.get = lambda key, default=None: dict.get(doc, key, default)
	return doc


class TestStandaloneReturnCosting(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_item(PRICED, valuation_rate=1116.0)
		make_item(UNPRICED)

	def test_only_a_standalone_return_that_moves_stock_is_ours(self):
		self.assertTrue(is_standalone_return(invoice([])))
		self.assertFalse(is_standalone_return(invoice([], is_return=0)))
		self.assertFalse(is_standalone_return(invoice([], return_against="SI-0001")))
		self.assertFalse(is_standalone_return(invoice([], update_stock=0)))

	def test_fallback_rate_prefers_the_valuation_rate(self):
		make_item(PRICED, valuation_rate=1116.0, standard_rate=50.0)
		self.assertEqual(fallback_rate(PRICED), 1116.0)
		make_item(PRICED, valuation_rate=0.0, standard_rate=50.0)
		self.assertEqual(fallback_rate(PRICED), 50.0)
		make_item(PRICED, valuation_rate=1116.0, standard_rate=0.0)

	def test_an_item_erpnext_cannot_price_is_costed_from_the_item_master(self):
		r = row(PRICED)
		doc = invoice([r])
		held = hold_rows(doc)
		self.assertEqual(r.allow_zero_valuation_rate, 1, "ERPNext must not stop on this row")
		r.incoming_rate = 0  # what ERPNext leaves behind when the ledger has nothing
		release_rows(held)
		self.assertEqual(r.incoming_rate, 1116.0)
		self.assertEqual(r.allow_zero_valuation_rate, 0, "the user's own flag must be given back")

	def test_a_rate_erpnext_found_in_the_ledger_is_left_alone(self):
		r = row(PRICED)
		held = hold_rows(invoice([r]))
		r.incoming_rate = 1255.0  # priced from the Stock Ledger
		release_rows(held)
		self.assertEqual(r.incoming_rate, 1255.0)

	def test_an_item_with_no_rate_anywhere_still_stops(self):
		r = row(UNPRICED)
		self.assertEqual(hold_rows(invoice([r])), [])
		self.assertFalse(r.get("allow_zero_valuation_rate"))

	def test_a_zero_rate_the_user_asked_for_is_respected(self):
		r = row(PRICED, allow_zero_valuation_rate=1)
		self.assertEqual(hold_rows(invoice([r])), [])
		self.assertEqual(r.allow_zero_valuation_rate, 1)

	def test_an_ordinary_invoice_is_untouched(self):
		r = row(PRICED)
		self.assertEqual(hold_rows(invoice([r], is_return=0)), [])
		self.assertFalse(r.get("allow_zero_valuation_rate"))

	def test_a_return_against_an_invoice_is_untouched(self):
		r = row(PRICED)
		self.assertEqual(hold_rows(invoice([r], return_against="SI-0001")), [])
		self.assertFalse(r.get("allow_zero_valuation_rate"))

	def test_a_non_stock_item_is_untouched(self):
		code = make_item("_Test CDN Return Service Item", valuation_rate=100.0, is_stock_item=0)
		r = row(code)
		self.assertEqual(hold_rows(invoice([r])), [])
