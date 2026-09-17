"""Whitelisted methods behind the Dispatch page."""

import frappe
from frappe import _
from frappe.utils import cint, date_diff, nowdate

from chundakadan.dispatch import constants as C
from chundakadan.dispatch.sync import sync_transport

LIST_FIELDS = [
	"name",
	"sales_invoice",
	"posting_date",
	"customer",
	"customer_name",
	"contact_mobile",
	"grand_total",
	"dispatch_status",
	"pending_reason",
	"pending_remarks",
	"transporter",
	"transporter_name",
	"gst_transporter_id",
	"vehicle_no",
	"lr_no",
	"lr_date",
	"driver_name",
	"mode_of_transport",
	"dispatched_on",
	"expected_delivery",
	"expected_delivery_date",
	"delivery_confirmed_on",
	"delivery_confirmed_by",
	"delivery_remarks",
	"ewaybill_sync_status",
	"ewaybill_sync_error",
]

TAB_ORDER = {
	"pending": "posting_date asc",
	"followup": "expected_delivery_date asc",
	"dispatched": "dispatched_on desc",
	"not_delivered": "expected_delivery_date asc",
	"delivered": "delivery_confirmed_on desc",
}


def _base_filters(filters):
	filters = frappe.parse_json(filters) if filters else {}
	conditions = [["invoice_cancelled", "=", 0]]
	if filters.get("from_date"):
		conditions.append(["posting_date", ">=", filters["from_date"]])
	if filters.get("to_date"):
		conditions.append(["posting_date", "<=", filters["to_date"]])
	if filters.get("customer"):
		conditions.append(["customer", "=", filters["customer"]])
	if filters.get("transporter"):
		conditions.append(["transporter", "=", filters["transporter"]])
	or_filters = None
	if filters.get("search"):
		like = f"%{filters['search']}%"
		or_filters = [["sales_invoice", "like", like], ["customer_name", "like", like]]
	return conditions, or_filters


def _tab_filters(tab):
	if tab == "pending":
		return [["dispatch_status", "=", C.PENDING]]
	if tab == "followup":
		return [
			["dispatch_status", "in", [C.DISPATCHED, C.NOT_DELIVERED]],
			["expected_delivery_date", "<=", nowdate()],
		]
	if tab == "dispatched":
		return [["dispatch_status", "=", C.DISPATCHED]]
	if tab == "not_delivered":
		return [["dispatch_status", "=", C.NOT_DELIVERED]]
	if tab == "delivered":
		return [["dispatch_status", "in", [C.DELIVERED, C.PICKUP]]]
	frappe.throw(_("Unknown tab {0}").format(tab))


def _count(conditions, or_filters):
	return len(frappe.get_all("Dispatch Log", filters=conditions, or_filters=or_filters, pluck="name"))


@frappe.whitelist()
def get_counts(filters=None):
	frappe.has_permission("Dispatch Log", "read", throw=True)
	base, or_filters = _base_filters(filters)
	counts = {tab: _count(base + _tab_filters(tab), or_filters) for tab in ("pending", "followup", "dispatched", "not_delivered")}
	counts["delivered_today"] = _count(
		base
		+ [
			["dispatch_status", "in", [C.DELIVERED, C.PICKUP]],
			["delivery_confirmed_on", ">=", nowdate()],
		],
		or_filters,
	)
	return counts


@frappe.whitelist()
def get_logs(tab, filters=None, start=0, page_length=50):
	frappe.has_permission("Dispatch Log", "read", throw=True)
	base, or_filters = _base_filters(filters)
	rows = frappe.get_all(
		"Dispatch Log",
		filters=base + _tab_filters(tab),
		or_filters=or_filters,
		fields=LIST_FIELDS,
		order_by=TAB_ORDER[tab],
		start=cint(start),
		page_length=cint(page_length) or 50,
	)
	today = nowdate()
	for row in rows:
		row["days_pending"] = date_diff(today, row.posting_date) if row.posting_date else 0
	return rows


def _get_log(log):
	doc = frappe.get_doc("Dispatch Log", log)
	doc.check_permission("write")
	if doc.invoice_cancelled:
		frappe.throw(_("Sales Invoice {0} is cancelled.").format(doc.sales_invoice))
	return doc


def _require_status(doc, *statuses):
	if doc.dispatch_status not in statuses:
		frappe.throw(
			_("{0} is {1}; this action needs status {2}.").format(
				doc.sales_invoice, doc.dispatch_status, " / ".join(statuses)
			)
		)


def _set_transport(doc, transporter, vehicle_no, lr_no, lr_date, driver_name, mode_of_transport):
	doc.transporter = transporter
	doc.vehicle_no = vehicle_no
	doc.lr_no = lr_no
	doc.lr_date = lr_date or None
	doc.driver_name = driver_name
	doc.mode_of_transport = mode_of_transport or "Road"
	supplier = frappe.db.get_value("Supplier", transporter, ["supplier_name", "gst_transporter_id"], as_dict=True) if transporter else None
	doc.transporter_name = supplier.supplier_name if supplier else None
	doc.gst_transporter_id = supplier.gst_transporter_id if supplier else None


def _result(doc):
	doc.reload()
	return {"name": doc.name, "dispatch_status": doc.dispatch_status, "ewaybill_sync_status": doc.ewaybill_sync_status}


@frappe.whitelist()
def set_pending_reason(log, reason, remarks=None):
	if reason not in C.PENDING_REASONS:
		frappe.throw(_("Invalid pending reason: {0}").format(reason))
	doc = _get_log(log)
	_require_status(doc, C.PENDING)
	doc.pending_reason = reason
	doc.pending_remarks = remarks
	doc.save()
	return _result(doc)


@frappe.whitelist()
def mark_dispatched(
	log,
	transporter,
	expected_delivery,
	vehicle_no=None,
	lr_no=None,
	lr_date=None,
	driver_name=None,
	mode_of_transport="Road",
	expected_delivery_date=None,
):
	doc = _get_log(log)
	_require_status(doc, C.PENDING)
	_set_transport(doc, transporter, vehicle_no, lr_no, lr_date, driver_name, mode_of_transport)
	doc.expected_delivery = expected_delivery
	doc.expected_delivery_date = expected_delivery_date or None
	doc.dispatch_status = C.DISPATCHED
	doc.save()
	return _result(doc)


@frappe.whitelist()
def update_transport(
	log,
	transporter,
	expected_delivery,
	vehicle_no=None,
	lr_no=None,
	lr_date=None,
	driver_name=None,
	mode_of_transport="Road",
	expected_delivery_date=None,
):
	doc = _get_log(log)
	_require_status(doc, C.DISPATCHED)
	_set_transport(doc, transporter, vehicle_no, lr_no, lr_date, driver_name, mode_of_transport)
	doc.expected_delivery = expected_delivery
	if expected_delivery_date:
		doc.expected_delivery_date = expected_delivery_date
	doc.save()
	return _result(doc)


@frappe.whitelist()
def mark_customer_pickup(log, remarks=None):
	doc = _get_log(log)
	_require_status(doc, C.PENDING)
	doc.dispatch_status = C.PICKUP
	doc.delivery_remarks = remarks
	doc.save()
	return _result(doc)


@frappe.whitelist()
def confirm_delivery(log, delivered, remarks=None, new_expected_date=None):
	delivered = bool(cint(frappe.parse_json(delivered) if isinstance(delivered, str) else delivered))
	doc = _get_log(log)
	_require_status(doc, C.DISPATCHED, C.NOT_DELIVERED)
	doc.delivery_remarks = remarks
	if delivered:
		doc.dispatch_status = C.DELIVERED
	else:
		if not new_expected_date:
			frappe.throw(_("Enter the new expected delivery date."))
		doc.dispatch_status = C.NOT_DELIVERED
		doc.expected_delivery_date = new_expected_date
	doc.save()
	return _result(doc)


@frappe.whitelist()
def retry_sync(log):
	doc = _get_log(log)
	_require_status(doc, C.DISPATCHED)
	sync_transport(doc)
	return _result(doc)


TRANSPORTER_GROUP = "Transporter"


def _transporter_group():
	if not frappe.db.exists("Supplier Group", TRANSPORTER_GROUP):
		frappe.get_doc(
			{
				"doctype": "Supplier Group",
				"supplier_group_name": TRANSPORTER_GROUP,
				"parent_supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 1, "parent_supplier_group": ["in", ["", None]]}, "name"),
			}
		).insert(ignore_permissions=True)
	return TRANSPORTER_GROUP


@frappe.whitelist()
def create_transporter(transporter_name, gst_transporter_id=None):
	"""Let a dispatcher add a transport partner without full Supplier rights.

	Only creates (or flags) a Supplier with Is Transporter ticked; nothing else
	about suppliers is exposed. An existing supplier with the same name is
	reused and marked as a transporter instead of creating a duplicate.
	"""
	frappe.has_permission("Dispatch Log", "write", throw=True)
	transporter_name = (transporter_name or "").strip()
	if not transporter_name:
		frappe.throw(_("Enter the transporter name."))
	gst_transporter_id = (gst_transporter_id or "").strip().upper() or None

	existing = frappe.db.get_value("Supplier", {"supplier_name": transporter_name}, "name")
	if existing:
		updates = {"is_transporter": 1}
		if gst_transporter_id and not frappe.db.get_value("Supplier", existing, "gst_transporter_id"):
			updates["gst_transporter_id"] = gst_transporter_id
		doc = frappe.get_doc("Supplier", existing)
		doc.update(updates)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": transporter_name,
				"supplier_group": _transporter_group(),
				"supplier_type": "Company",
				"is_transporter": 1,
				"gst_transporter_id": gst_transporter_id,
			}
		).insert(ignore_permissions=True)
	return {"name": doc.name, "supplier_name": doc.supplier_name, "gst_transporter_id": doc.gst_transporter_id}
