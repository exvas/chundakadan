# Copyright (c) 2026, Chundakadan and contributors
"""Who sent the day's work summary, and who did not.

One row per employee per working day in the range. Days that are a holiday
for that employee, or covered by approved leave, are left out -- they are
not missing summaries.
"""

import frappe
from frappe import _
from frappe.utils import add_days, getdate

from chundakadan.chundakadan.api import work_summary as ws

MAX_DAYS = 62


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not (filters.from_date and filters.to_date):
		frappe.throw(_("Select From Date and To Date"))
	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date"))
	days = (getdate(filters.to_date) - getdate(filters.from_date)).days + 1
	if days > MAX_DAYS:
		frappe.throw(_("Pick a range of {0} days or fewer").format(MAX_DAYS))
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "work_date", "fieldtype": "Date", "width": 100},
		{"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 200},
		{"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 170},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 140},
		{"label": _("Summary"), "fieldname": "summary", "fieldtype": "Link", "options": "Daily Work Summary", "width": 140},
		{"label": _("Tasks"), "fieldname": "task_count", "fieldtype": "Int", "width": 70},
		{"label": _("Waiting On"), "fieldname": "current_approver", "fieldtype": "Link", "options": "User", "width": 180},
	]


def get_data(filters):
	employee_filters = {"status": "Active"}
	if filters.get("department"):
		employee_filters["department"] = filters.department
	if filters.get("company"):
		employee_filters["company"] = filters.company
	if filters.get("employee"):
		employee_filters["name"] = filters.employee
	employees = frappe.get_all(
		"Employee", filters=employee_filters,
		fields=["name", "employee_name", "department"],
	)
	if not employees:
		return []

	summaries = {}
	for row in frappe.get_all(
		"Daily Work Summary",
		filters={
			"work_date": ["between", [filters.from_date, filters.to_date]],
			"employee": ["in", [e.name for e in employees]],
			"docstatus": ["<", 2],
		},
		fields=["name", "employee", "work_date", "custom_approval_status", "current_approver"],
	):
		summaries[(row.employee, str(row.work_date))] = row

	task_counts = _task_counts([r.name for r in summaries.values()])

	only_missing = bool(filters.get("only_missing"))
	data = []
	day = getdate(filters.from_date)
	last = getdate(filters.to_date)
	while day <= last:
		for employee in employees:
			found = summaries.get((employee.name, str(day)))
			if not found:
				if ws._is_holiday(employee.name, day) or ws._on_leave(employee.name, day):
					continue
				data.append({
					"work_date": day, "employee": employee.name,
					"employee_name": employee.employee_name, "department": employee.department,
					"status": _("Not Submitted"), "summary": None, "task_count": 0,
					"current_approver": None,
				})
				continue
			if only_missing and found.custom_approval_status not in (ws.STATUS_DRAFT, ws.STATUS_RETURNED):
				continue
			data.append({
				"work_date": day, "employee": employee.name,
				"employee_name": employee.employee_name, "department": employee.department,
				"status": found.custom_approval_status,
				"summary": found.name,
				"task_count": task_counts.get(found.name, 0),
				"current_approver": found.current_approver,
			})
		day = add_days(day, 1)
	return data


def _task_counts(names):
	if not names:
		return {}
	rows = frappe.db.sql(
		"""select parent, count(*) as tasks from `tabDaily Work Summary Task`
		where parenttype = 'Daily Work Summary' and parent in %(names)s
		group by parent""",
		{"names": names}, as_dict=True,
	)
	return {r.parent: r.tasks for r in rows}
