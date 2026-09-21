# Copyright (c) 2026, Chundakadan and contributors
"""Post dated cheques on hand, with status and days to the cheque date."""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Cheque Date"), "fieldname": "cheque_date", "fieldtype": "Date", "width": 100},
		{"label": _("Cheque No"), "fieldname": "cheque_no", "fieldtype": "Data", "width": 110},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 230},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{"label": _("Days to Cheque Date"), "fieldname": "days_to_due", "fieldtype": "Int", "width": 90},
		{"label": _("Customer's Bank"), "fieldname": "bank_name", "fieldtype": "Data", "width": 140},
		{"label": _("Sales Person"), "fieldname": "sales_person", "fieldtype": "Link", "options": "Sales Person", "width": 130},
		{"label": _("Invoices"), "fieldname": "invoices", "fieldtype": "Data", "width": 180},
		{"label": _("Payment Entry"), "fieldname": "payment_entry", "fieldtype": "Link", "options": "Payment Entry", "width": 140},
		{"label": _("PDC"), "fieldname": "name", "fieldtype": "Link", "options": "Post Dated Cheque", "width": 120},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 100},
	]


def get_data(filters):
	conditions = {"docstatus": ["<", 2]}
	if filters.get("company"):
		conditions["company"] = filters.company
	if filters.get("customer"):
		conditions["customer"] = filters.customer
	if filters.get("status"):
		conditions["status"] = filters.status
	if filters.get("sales_person"):
		conditions["sales_person"] = filters.sales_person
	if filters.get("from_date") and filters.get("to_date"):
		conditions["cheque_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.get("from_date"):
		conditions["cheque_date"] = [">=", filters.from_date]
	elif filters.get("to_date"):
		conditions["cheque_date"] = ["<=", filters.to_date]

	rows = frappe.get_all(
		"Post Dated Cheque",
		filters=conditions,
		fields=["name", "cheque_date", "cheque_no", "customer", "customer_name", "amount", "posting_date", "status", "bank_name", "sales_person", "payment_entry"],
		order_by="cheque_date asc, creation asc",
	)
	if not rows:
		return []

	references = frappe.get_all(
		"Post Dated Cheque Reference",
		filters={"parent": ["in", [r.name for r in rows]]},
		fields=["parent", "sales_invoice"],
	)
	by_cheque = {}
	for ref in references:
		by_cheque.setdefault(ref.parent, []).append(ref.sales_invoice)

	today = getdate(nowdate())
	for row in rows:
		row["invoices"] = ", ".join(by_cheque.get(row.name, []))
		row["days_to_due"] = date_diff(row.cheque_date, today) if row.cheque_date else None
	return rows
