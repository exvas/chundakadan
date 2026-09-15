"""Sales Invoice hooks that create and maintain Dispatch Logs."""

import frappe

from chundakadan.dispatch import constants as C


def is_in_scope(invoice) -> bool:
	return (
		invoice.get("company") == C.COMPANY
		and invoice.get("docstatus") == 1
		and not invoice.get("is_return")
		and invoice.get("is_opening") != "Yes"
	)


def _contact_mobile(invoice) -> str:
	mobile = invoice.get("contact_mobile")
	if not mobile and invoice.get("customer_address"):
		mobile = frappe.db.get_value("Address", invoice.get("customer_address"), "phone")
	return mobile or ""


def build_log(invoice):
	return frappe.get_doc(
		{
			"doctype": "Dispatch Log",
			"sales_invoice": invoice.name,
			"company": invoice.company,
			"customer": invoice.customer,
			"customer_name": invoice.customer_name,
			"contact_mobile": _contact_mobile(invoice),
			"posting_date": invoice.posting_date,
			"grand_total": invoice.grand_total,
			"dispatch_status": C.PENDING,
		}
	)


def create_dispatch_log(doc, method=None):
	"""on_submit on Sales Invoice. Never blocks the submit."""
	if not is_in_scope(doc):
		return
	try:
		if frappe.db.exists("Dispatch Log", {"sales_invoice": doc.name}):
			return
		build_log(doc).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title=f"Dispatch Log creation failed for {doc.name}")


def mark_invoice_cancelled(doc, method=None):
	"""on_cancel on Sales Invoice."""
	name = frappe.db.get_value("Dispatch Log", {"sales_invoice": doc.name})
	if name:
		frappe.db.set_value("Dispatch Log", name, "invoice_cancelled", 1)


def backfill_dispatch_logs(from_date=C.BACKFILL_FROM) -> int:
	names = frappe.get_all(
		"Sales Invoice",
		filters={
			"company": C.COMPANY,
			"docstatus": 1,
			"is_return": 0,
			"is_opening": ["!=", "Yes"],
			"posting_date": [">=", from_date],
		},
		pluck="name",
	)
	created = 0
	for name in names:
		if frappe.db.exists("Dispatch Log", {"sales_invoice": name}):
			continue
		build_log(frappe.get_doc("Sales Invoice", name)).insert(ignore_permissions=True)
		created += 1
	return created
