"""Tests for dispatch events, transport sync and page API."""

from unittest import SkipTest
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from chundakadan.chundakadan.doctype.dispatch_log.test_dispatch_log import (
	ensure_transporter,
	fresh_log,
	in_scope_invoices,
)
from chundakadan.dispatch import api, constants as C
from chundakadan.dispatch.events import (
	backfill_dispatch_logs,
	create_dispatch_log,
	is_in_scope,
	mark_invoice_cancelled,
)
from chundakadan.dispatch.setup import ensure_dispatch_role, ensure_sales_invoice_field
from chundakadan.dispatch.sync import sync_transport

E_WAYBILL = "india_compliance.gst_india.utils.e_waybill"


class TestDispatch(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		ensure_dispatch_role()
		ensure_sales_invoice_field()
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.invoices = in_scope_invoices()
		if not cls.invoices:
			raise SkipTest("no in-scope Sales Invoice on this site")
		cls.transporter = ensure_transporter()

	def tearDown(self):
		frappe.set_user("Administrator")

	# ---- events -------------------------------------------------------

	def test_is_in_scope(self):
		base = {"company": C.COMPANY, "docstatus": 1, "is_return": 0, "is_opening": "No"}
		self.assertTrue(is_in_scope(frappe._dict(base)))
		self.assertFalse(is_in_scope(frappe._dict(base, company="Chundakadan Home Stop")))
		self.assertFalse(is_in_scope(frappe._dict(base, is_return=1)))
		self.assertFalse(is_in_scope(frappe._dict(base, is_opening="Yes")))
		self.assertFalse(is_in_scope(frappe._dict(base, docstatus=2)))

	def test_create_dispatch_log_is_idempotent(self):
		name = self.invoices[0]
		frappe.db.delete("Dispatch Log", {"sales_invoice": name})
		invoice = frappe.get_doc("Sales Invoice", name)
		create_dispatch_log(invoice)
		create_dispatch_log(invoice)
		self.assertEqual(frappe.db.count("Dispatch Log", {"sales_invoice": name}), 1)

	def test_create_skips_out_of_scope_invoice(self):
		name = self.invoices[0]
		frappe.db.delete("Dispatch Log", {"sales_invoice": name})
		invoice = frappe.get_doc("Sales Invoice", name)
		invoice.company = "Chundakadan Home Stop"
		create_dispatch_log(invoice)
		self.assertEqual(frappe.db.count("Dispatch Log", {"sales_invoice": name}), 0)

	def test_mark_invoice_cancelled(self):
		log = fresh_log(self.invoices[0])
		mark_invoice_cancelled(frappe.get_doc("Sales Invoice", log.sales_invoice))
		self.assertEqual(frappe.db.get_value("Dispatch Log", log.name, "invoice_cancelled"), 1)

	def test_backfill_creates_missing_logs(self):
		filters = {
			"company": C.COMPANY,
			"docstatus": 1,
			"is_return": 0,
			"is_opening": ["!=", "Yes"],
			"posting_date": [">=", C.BACKFILL_FROM],
		}
		names = frappe.get_all("Sales Invoice", filters=filters, pluck="name")
		frappe.db.delete("Dispatch Log", {"sales_invoice": ["in", names or [""]]})
		created = backfill_dispatch_logs()
		self.assertEqual(created, len(names))
		self.assertEqual(backfill_dispatch_logs(), 0)

	# ---- sync ---------------------------------------------------------

	def _dispatched_log_with_ewaybill(self, gst_transporter_id=None):
		log = fresh_log(self.invoices[0])
		frappe.db.set_value("Sales Invoice", log.sales_invoice, "ewaybill", "331000000001", update_modified=False)
		log.transporter = self.transporter
		log.gst_transporter_id = gst_transporter_id
		log.vehicle_no = "KL10AB1234"
		log.lr_no = "LR-1"
		log.expected_delivery = "Next Day"
		log.dispatch_status = C.DISPATCHED
		return log

	def test_sync_with_ewaybill_updates_vehicle_on_portal(self):
		log = self._dispatched_log_with_ewaybill()
		with patch(f"{E_WAYBILL}.update_vehicle_info") as vehicle, patch(f"{E_WAYBILL}.update_transporter") as transporter:
			log.save()
		vehicle.assert_called_once()
		values = vehicle.call_args.kwargs["values"]
		self.assertEqual(values["vehicle_no"], "KL10AB1234")
		self.assertEqual(values["lr_no"], "LR-1")
		transporter.assert_not_called()  # no GST transporter id
		self.assertEqual(frappe.db.get_value("Sales Invoice", log.sales_invoice, "transporter"), self.transporter)
		self.assertEqual(frappe.db.get_value("Dispatch Log", log.name, "ewaybill_sync_status"), "Synced")

	def test_sync_calls_update_transporter_when_id_present(self):
		log = self._dispatched_log_with_ewaybill()
		# Every save/sync of a log whose invoice has an e-Waybill must stay patched:
		# unpatched calls would reach the live e-Waybill portal.
		with patch(f"{E_WAYBILL}.update_vehicle_info"), patch(f"{E_WAYBILL}.update_transporter") as transporter:
			log.save()
			transporter.reset_mock()
			# fetch_from blanks the id on save, so set it after saving and sync directly
			log.gst_transporter_id = "32AAGFC3363E1ZX"
			sync_transport(log)
		transporter.assert_called_once()
		self.assertEqual(transporter.call_args.kwargs["values"]["gst_transporter_id"], "32AAGFC3363E1ZX")

	def test_sync_failure_marks_failed(self):
		log = self._dispatched_log_with_ewaybill()
		with patch(f"{E_WAYBILL}.update_vehicle_info", side_effect=Exception("portal down")):
			log.save()
		row = frappe.db.get_value("Dispatch Log", log.name, ["dispatch_status", "ewaybill_sync_status", "ewaybill_sync_error"], as_dict=True)
		self.assertEqual(row.dispatch_status, C.DISPATCHED)
		self.assertEqual(row.ewaybill_sync_status, "Failed")
		self.assertIn("portal down", row.ewaybill_sync_error)

	# ---- api ----------------------------------------------------------

	def test_api_full_flow(self):
		log = fresh_log(self.invoices[0])
		api.set_pending_reason(log.name, "Payment Pending", "waiting for cheque")
		self.assertEqual(frappe.db.get_value("Dispatch Log", log.name, "pending_reason"), "Payment Pending")

		pending = api.get_logs("pending", filters={"search": log.sales_invoice})
		self.assertIn(log.name, [r.name for r in pending])
		self.assertIn("days_pending", pending[0])

		result = api.mark_dispatched(log.name, self.transporter, "Next Day", vehicle_no="KL10AB1234")
		self.assertEqual(result["dispatch_status"], C.DISPATCHED)

		with self.assertRaises(frappe.ValidationError):
			api.confirm_delivery(log.name, delivered=0)

		api.confirm_delivery(log.name, delivered=0, remarks="shop closed", new_expected_date=nowdate())
		followup = api.get_logs("followup", filters={"search": log.sales_invoice})
		self.assertIn(log.name, [r.name for r in followup])

		api.confirm_delivery(log.name, delivered="true", remarks="received")
		self.assertEqual(frappe.db.get_value("Dispatch Log", log.name, "dispatch_status"), C.DELIVERED)
		counts = api.get_counts(filters={"search": log.sales_invoice})
		self.assertEqual(counts["delivered_today"], 1)

	def test_api_rejects_invalid_reason_and_wrong_status(self):
		log = fresh_log(self.invoices[0])
		with self.assertRaises(frappe.ValidationError):
			api.set_pending_reason(log.name, "Rain")
		with self.assertRaises(frappe.ValidationError):
			api.confirm_delivery(log.name, delivered=1)

	def test_api_customer_pickup(self):
		log = fresh_log(self.invoices[0])
		api.mark_customer_pickup(log.name, "collected at counter")
		delivered = api.get_logs("delivered", filters={"search": log.sales_invoice})
		self.assertIn(log.name, [r.name for r in delivered])

	def test_api_blocks_cancelled_invoice(self):
		log = fresh_log(self.invoices[0])
		frappe.db.set_value("Dispatch Log", log.name, "invoice_cancelled", 1)
		with self.assertRaises(frappe.ValidationError):
			api.mark_customer_pickup(log.name)

	def test_api_requires_permission(self):
		log = fresh_log(self.invoices[0])
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			api.get_counts()
		with self.assertRaises(frappe.PermissionError):
			api.mark_customer_pickup(log.name)
