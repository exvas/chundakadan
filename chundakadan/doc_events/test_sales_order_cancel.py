"""A billed Sales Order must not be cancellable.

ERPNext stops the cancel only while the invoice is still a draft, so an order
that has been invoiced and sent could be cancelled — and then the invoice
could not be, because cancelling it updates the order's reserved quantity and
that refuses to touch a cancelled order. One cancelled, one not, and nothing
on screen to say why.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events.sales_order import (
	_submitted_documents_against,
	refuse_cancel_when_billed_or_delivered,
)

ORDER = "_TEST-CDN-SO-CANCEL"


class TestSalesOrderCancelGuard(FrappeTestCase):
	def _guard(self, blocking):
		doc = frappe._dict({"name": ORDER})
		with patch(
			"chundakadan.doc_events.sales_order._submitted_documents_against",
			return_value=blocking,
		):
			refuse_cancel_when_billed_or_delivered(doc)

	def test_an_order_with_nothing_against_it_cancels(self):
		self._guard([])  # no throw

	def test_a_submitted_invoice_stops_the_cancel(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			self._guard([("Sales Invoice", "SI-CA-26-1966")])
		self.assertIn("SI-CA-26-1966", str(caught.exception))

	def test_a_submitted_delivery_note_stops_it_too(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			self._guard([("Delivery Note", "DN-CA-26-0001")])
		self.assertIn("DN-CA-26-0001", str(caught.exception))

	def test_the_message_names_every_document_in_the_way(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			self._guard([("Sales Invoice", "SI-1"), ("Delivery Note", "DN-1")])
		message = str(caught.exception)
		self.assertIn("SI-1", message)
		self.assertIn("DN-1", message)

	def test_a_draft_invoice_is_not_counted_erpnext_already_stops_that(self):
		"""Only submitted documents; ERPNext's own check covers drafts, and
		counting them here would give two different refusals for one case."""
		order = frappe.db.sql_list(
			"""select distinct sii.sales_order from `tabSales Invoice Item` sii
			   join `tabSales Invoice` si on si.name = sii.parent
			  where si.docstatus = 0 and ifnull(sii.sales_order, '') <> '' limit 1"""
		)
		if not order:
			self.skipTest("no draft invoice against an order on this site")
		self.assertEqual(_submitted_documents_against(order[0]), [])

	def test_the_lookup_finds_a_real_submitted_invoice(self):
		row = frappe.db.sql(
			"""select sii.sales_order, si.name from `tabSales Invoice Item` sii
			   join `tabSales Invoice` si on si.name = sii.parent
			  where si.docstatus = 1 and ifnull(sii.sales_order, '') <> '' limit 1""",
			as_dict=True,
		)
		if not row:
			self.skipTest("no submitted invoice against an order on this site")
		found = _submitted_documents_against(row[0].sales_order)
		self.assertIn(("Sales Invoice", row[0].name), found)
