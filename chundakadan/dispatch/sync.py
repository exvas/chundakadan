"""Copy dispatch transport details to the Sales Invoice and its e-Waybill."""

import frappe
from frappe.utils import cstr

from chundakadan.dispatch import constants as C


def _as_administrator(fn, **kwargs):
	# India Compliance checks "submit" permission on the invoice; the Dispatch
	# User only has read. The API layer has already checked Dispatch Log write.
	user = frappe.session.user
	try:
		frappe.set_user("Administrator")
		return fn(**kwargs)
	finally:
		frappe.set_user(user)


def _place_of_dispatch(invoice):
	city, state = None, None
	if invoice.company_address:
		city, state = frappe.db.get_value("Address", invoice.company_address, ["city", "state"]) or (None, None)
	return city or "Kerala", state or "Kerala"


def _sync_ewaybill(log, invoice):
	from india_compliance.gst_india.utils import e_waybill

	if log.gst_transporter_id:
		_as_administrator(
			e_waybill.update_transporter,
			doctype="Sales Invoice",
			docname=invoice.name,
			values={
				"transporter": log.transporter,
				"gst_transporter_id": log.gst_transporter_id,
				"update_e_waybill_data": 0,
			},
		)
	else:
		frappe.db.set_value(
			"Sales Invoice",
			invoice.name,
			{"transporter": log.transporter, "transporter_name": log.transporter_name},
			update_modified=False,
		)

	if log.vehicle_no or log.lr_no:
		place, state = _place_of_dispatch(invoice)
		_as_administrator(
			e_waybill.update_vehicle_info,
			doctype="Sales Invoice",
			docname=invoice.name,
			values={
				"vehicle_no": log.vehicle_no or "",
				"lr_no": log.lr_no,
				"lr_date": log.lr_date,
				"mode_of_transport": log.mode_of_transport or "Road",
				"gst_vehicle_type": "Regular",
				"place_of_change": place,
				"state": state,
				"reason": "Others" if invoice.vehicle_no else "First Time",
				"remark": "Updated from Dispatch",
			},
		)

	frappe.db.set_value(
		"Sales Invoice", invoice.name, "driver_name", log.driver_name, update_modified=False
	)


def sync_transport(log) -> str:
	"""Returns the resulting ewaybill_sync_status and stores it on the log."""
	invoice = frappe.db.get_value(
		"Sales Invoice",
		log.sales_invoice,
		["name", "ewaybill", "vehicle_no", "company_address"],
		as_dict=True,
	)
	if not invoice:
		return log.ewaybill_sync_status

	try:
		if invoice.ewaybill:
			_sync_ewaybill(log, invoice)
			status = "Synced"
		else:
			frappe.db.set_value(
				"Sales Invoice",
				invoice.name,
				{field: log.get(field) for field in C.TRANSPORT_FIELDS},
				update_modified=False,
			)
			status = "Not Required"
		error = ""
	except Exception as e:
		frappe.log_error(title=f"Dispatch transport sync failed for {log.sales_invoice}")
		status, error = "Failed", cstr(e)[:1000]

	log.db_set({"ewaybill_sync_status": status, "ewaybill_sync_error": error}, update_modified=False)
	return status
