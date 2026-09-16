"""Auto Delivery Note on Sales Invoice submit."""

from unittest import SkipTest
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events.sales_invoice import auto_create_delivery_note, backfill_delivery_notes

test_ignore = ["Sales Invoice", "Customer", "Supplier", "Company", "User"]

BASE = {
	"company": "Chundakadan Agencies",
	"docstatus": 1,
	"is_return": 0,
	"is_opening": ["!=", "Yes"],
}


def _invoice(update_stock):
	"""A submitted invoice that has no Delivery Note linked to it yet."""
	linked = frappe.get_all(
		"Delivery Note Item",
		filters={"against_sales_invoice": ["is", "set"], "docstatus": ["<", 2]},
		pluck="against_sales_invoice",
		distinct=True,
	)
	filters = dict(BASE, update_stock=update_stock)
	if linked:
		filters["name"] = ["not in", linked]
	name = frappe.db.get_value("Sales Invoice", filters, "name", order_by="posting_date desc")
	if not name:
		raise SkipTest(f"no free submitted invoice with update_stock={update_stock}")
	return frappe.get_doc("Sales Invoice", name)


def _notes_for(invoice):
	return frappe.get_all(
		"Delivery Note Item",
		filters={"against_sales_invoice": invoice.name, "docstatus": ["<", 2]},
		pluck="parent",
		distinct=True,
	)


class TestAutoDeliveryNote(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

	def test_creates_and_submits_note(self):
		invoice = _invoice(0)
		auto_create_delivery_note(invoice)
		notes = _notes_for(invoice)
		self.assertEqual(len(notes), 1)
		note = frappe.get_doc("Delivery Note", notes[0])
		self.assertEqual(note.docstatus, 1)
		self.assertEqual(note.customer, invoice.customer)
		self.assertEqual(str(note.posting_date), str(invoice.posting_date))
		self.assertTrue(
			frappe.db.exists("Stock Ledger Entry", {"voucher_no": note.name, "is_cancelled": 0}),
			"delivery note should move stock",
		)

	def test_is_idempotent(self):
		invoice = _invoice(0)
		auto_create_delivery_note(invoice)
		auto_create_delivery_note(invoice)
		self.assertEqual(len(_notes_for(invoice)), 1)

	def test_skips_invoice_that_updated_stock(self):
		invoice = _invoice(1)
		auto_create_delivery_note(invoice)
		self.assertEqual(_notes_for(invoice), [])

	def test_skips_return_and_opening(self):
		invoice = _invoice(0)
		for field, value in (("is_return", 1), ("is_opening", "Yes")):
			doc = frappe.copy_doc(invoice)
			doc.name = invoice.name
			doc.set(field, value)
			auto_create_delivery_note(doc)
		self.assertEqual(_notes_for(invoice), [])

	def test_failure_does_not_raise(self):
		invoice = _invoice(0)
		with patch(
			"erpnext.accounts.doctype.sales_invoice.sales_invoice.make_delivery_note",
			side_effect=Exception("boom"),
		):
			auto_create_delivery_note(invoice)  # must not raise
		self.assertEqual(_notes_for(invoice), [])


	def test_backfill_dry_run_changes_nothing(self):
		invoice = _invoice(0)
		before = frappe.db.count("Delivery Note")
		result = backfill_delivery_notes(name_like=invoice.name, dry_run=1)
		self.assertEqual(result["created"], [invoice.name])
		self.assertTrue(result["dry_run"])
		self.assertEqual(frappe.db.count("Delivery Note"), before)

	def test_backfill_creates_and_submits_the_note(self):
		invoice = _invoice(0)
		result = backfill_delivery_notes(name_like=invoice.name)
		self.assertEqual(result["created"], [invoice.name])
		self.assertEqual(result["failed"], [])
		notes = _notes_for(invoice)
		self.assertEqual(len(notes), 1)
		self.assertEqual(frappe.db.get_value("Delivery Note", notes[0], "docstatus"), 1)

	def test_backfill_skips_an_invoice_that_already_has_a_note(self):
		invoice = _invoice(0)
		backfill_delivery_notes(name_like=invoice.name)
		again = backfill_delivery_notes(name_like=invoice.name)
		self.assertEqual(again["created"], [])
		self.assertEqual(again["skipped"], [invoice.name])
		self.assertEqual(len(_notes_for(invoice)), 1)
