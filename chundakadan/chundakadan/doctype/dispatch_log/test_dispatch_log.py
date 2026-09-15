# Copyright (c) 2026, Chundakadan and contributors
# For license information, please see license.txt

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate

from chundakadan.dispatch import constants as C
from chundakadan.dispatch.setup import ensure_dispatch_role, ensure_sales_invoice_field

# Tests use real submitted invoices on the site; don't generate ERPNext test records.
test_ignore = ["Sales Invoice", "Customer", "Supplier", "Company", "User"]

TRANSPORTER = "_Test Dispatch Transporter"


def in_scope_invoices(limit=3):
	"""Submitted Chundakadan Agencies invoices without an e-Waybill."""
	return frappe.get_all(
		"Sales Invoice",
		filters={
			"company": C.COMPANY,
			"docstatus": 1,
			"is_return": 0,
			"is_opening": ["!=", "Yes"],
			"ewaybill": ["is", "not set"],
		},
		pluck="name",
		order_by="posting_date desc",
		limit=limit,
	)


def ensure_transporter():
	if not frappe.db.exists("Supplier", TRANSPORTER):
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": TRANSPORTER,
				"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
				"is_transporter": 1,
			}
		).insert(ignore_permissions=True)
	return TRANSPORTER


def fresh_log(invoice_name):
	"""Delete any existing log for the invoice and create a new Pending one."""
	from chundakadan.dispatch.events import build_log

	for name in frappe.get_all("Dispatch Log", filters={"sales_invoice": invoice_name}, pluck="name"):
		frappe.delete_doc("Dispatch Log", name, force=1, ignore_permissions=True)
	return build_log(frappe.get_doc("Sales Invoice", invoice_name)).insert(ignore_permissions=True)


class TestDispatchLog(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		ensure_dispatch_role()
		ensure_sales_invoice_field()
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.invoices = in_scope_invoices()
		if not cls.invoices:
			raise unittest.SkipTest("no in-scope Sales Invoice on this site")
		cls.transporter = ensure_transporter()

	def _dispatch(self, log, **kw):
		log.transporter = kw.get("transporter", self.transporter)
		log.expected_delivery = kw.get("expected_delivery", "2 Days")
		log.vehicle_no = kw.get("vehicle_no", "KL10AB1234")
		log.dispatch_status = C.DISPATCHED
		log.save()
		return log

	def test_new_log_is_pending_and_mirrored_on_invoice(self):
		log = fresh_log(self.invoices[0])
		self.assertEqual(log.dispatch_status, C.PENDING)
		self.assertEqual(
			frappe.db.get_value("Sales Invoice", log.sales_invoice, "dispatch_status"), C.PENDING
		)

	def test_one_log_per_invoice(self):
		log = fresh_log(self.invoices[0])
		from chundakadan.dispatch.events import build_log

		with self.assertRaises(frappe.UniqueValidationError):
			build_log(frappe.get_doc("Sales Invoice", log.sales_invoice)).insert(ignore_permissions=True)

	def test_dispatch_requires_transporter(self):
		log = fresh_log(self.invoices[0])
		log.expected_delivery = "Next Day"
		log.dispatch_status = C.DISPATCHED
		with self.assertRaises(frappe.ValidationError):
			log.save()

	def test_dispatch_stamps_and_expected_date(self):
		log = self._dispatch(fresh_log(self.invoices[0]), expected_delivery="2 Days")
		self.assertEqual(log.dispatched_by, "Administrator")
		self.assertIsNotNone(log.dispatched_on)
		self.assertEqual(
			getdate(log.expected_delivery_date), add_days(getdate(log.dispatched_on), 2)
		)

	def test_changing_option_recomputes_date(self):
		log = self._dispatch(fresh_log(self.invoices[0]), expected_delivery="Next Day")
		log.expected_delivery = "After 2 Days"
		log.save()
		self.assertEqual(
			getdate(log.expected_delivery_date), add_days(getdate(log.dispatched_on), 3)
		)

	def test_invalid_transition_rejected(self):
		log = fresh_log(self.invoices[0])
		log.dispatch_status = C.DELIVERED
		with self.assertRaises(frappe.ValidationError):
			log.save()

	def test_delivered_after_dispatch_stamps_confirmation(self):
		log = self._dispatch(fresh_log(self.invoices[0]))
		log.dispatch_status = C.DELIVERED
		log.save()
		self.assertEqual(log.delivery_confirmed_by, "Administrator")
		self.assertIsNotNone(log.delivery_confirmed_on)

	def test_not_delivered_requires_date(self):
		log = self._dispatch(fresh_log(self.invoices[0]))
		log.dispatch_status = C.NOT_DELIVERED
		log.expected_delivery_date = None
		with self.assertRaises(frappe.ValidationError):
			log.save()

	def test_customer_pickup_closes_without_transporter(self):
		log = fresh_log(self.invoices[0])
		log.dispatch_status = C.PICKUP
		log.save()
		self.assertIsNotNone(log.delivery_confirmed_on)
		log.dispatch_status = C.DISPATCHED
		with self.assertRaises(frappe.ValidationError):
			log.save()

	def test_transport_copied_to_invoice_without_ewaybill(self):
		log = self._dispatch(fresh_log(self.invoices[0]), vehicle_no="KL10XY9999")
		invoice = frappe.db.get_value(
			"Sales Invoice", log.sales_invoice, ["transporter", "vehicle_no", "dispatch_status"], as_dict=True
		)
		self.assertEqual(invoice.transporter, self.transporter)
		self.assertEqual(invoice.vehicle_no, "KL10XY9999")
		self.assertEqual(invoice.dispatch_status, C.DISPATCHED)
		self.assertEqual(frappe.db.get_value("Dispatch Log", log.name, "ewaybill_sync_status"), "Not Required")
