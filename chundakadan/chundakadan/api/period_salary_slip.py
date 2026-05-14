# Copyright (c) 2026, Ashkar and contributors
# For license information, please see license.txt

import frappe


@frappe.whitelist()
def get_salary_slips(employee, from_date, to_date):
	"""
	Fetch submitted Salary Slips for a given employee within a date range.
	Filters: docstatus = 1 (Submitted), start_date >= from_date, end_date <= to_date.
	Returns: salary_slip name, start_date, end_date, net_pay ordered by start_date asc.
	"""
	salary_slips = frappe.db.get_all(
		"Salary Slip",
		filters={
			"employee": employee,
			"start_date": [">=", from_date],
			"end_date": ["<=", to_date],
			"docstatus": 1,
		},
		fields=["name as salary_slip", "start_date", "end_date", "net_pay"],
		order_by="start_date asc",
	)

	return salary_slips
