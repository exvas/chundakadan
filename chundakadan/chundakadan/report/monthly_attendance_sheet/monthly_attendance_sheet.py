# Copyright (c) 2026, Ashkar and contributors
# For license information, please see license.txt
#
# Overrides HRMS Monthly Attendance Sheet to collapse all shifts into a single
# row per employee instead of one row per shift.
#
# Only the three functions that form the call chain are redefined here
# (execute → get_data → get_rows).  Everything else is imported from HRMS so
# we stay in sync with upstream changes automatically.

import frappe
from frappe import _
from frappe.utils import cstr

from hrms.hr.report.monthly_attendance_sheet.monthly_attendance_sheet import (
	Filters,
	get_attendance_map,
	get_attendance_status_for_summarized_view,
	get_chart_data,
	get_columns,
	get_employee_related_details,
	get_entry_exits_summary,
	get_holiday_map,
	get_holiday_status,
	get_leave_summary,
	get_message,
	get_total_days_in_month,
	set_defaults_for_summarized_view,
	status_map,
)


def execute(filters: Filters | None = None) -> tuple:
	filters = frappe._dict(filters or {})

	if not (filters.month and filters.year):
		frappe.throw(_("Please select month and year."))

	if not filters.company:
		frappe.throw(_("Please select company."))

	from frappe.utils.nestedset import get_descendants_of

	if filters.company:
		filters.companies = [filters.company]
		if filters.include_company_descendants:
			filters.companies.extend(get_descendants_of("Company", filters.company))

	attendance_map = get_attendance_map(filters)
	if not attendance_map:
		frappe.msgprint(_("No attendance records found."), alert=True, indicator="orange")
		return [], [], None, None

	columns = get_columns(filters)
	data = get_data(filters, attendance_map)

	if not data:
		frappe.msgprint(
			_("No attendance records found for this criteria."), alert=True, indicator="orange"
		)
		return columns, [], None, None

	message = get_message() if not filters.summarized_view else ""
	chart = get_chart_data(attendance_map, filters)

	return columns, data, message, chart


def get_data(filters: Filters, attendance_map: dict) -> list[dict]:
	employee_details, group_by_param_values = get_employee_related_details(filters)
	holiday_map = get_holiday_map(filters)
	data = []

	if filters.group_by:
		group_by_column = frappe.scrub(filters.group_by)

		for value in group_by_param_values:
			if not value:
				continue

			records = get_rows(employee_details[value], filters, holiday_map, attendance_map)

			if records:
				data.append({group_by_column: value})
				data.extend(records)
	else:
		data = get_rows(employee_details, filters, holiday_map, attendance_map)

	return data


def get_rows(
	employee_details: dict, filters: Filters, holiday_map: dict, attendance_map: dict
) -> list[dict]:
	records = []
	default_holiday_list = frappe.get_cached_value("Company", filters.company, "default_holiday_list")

	for employee, details in employee_details.items():
		emp_holiday_list = details.holiday_list or default_holiday_list
		holidays = holiday_map.get(emp_holiday_list)

		if filters.summarized_view:
			attendance = get_attendance_status_for_summarized_view(
				employee, filters, holidays, details.joined_in_current_period, details.joined_date
			)
			if not attendance:
				continue

			leave_summary = get_leave_summary(employee, filters)
			entry_exits_summary = get_entry_exits_summary(employee, filters)

			row = {"employee": employee, "employee_name": details.employee_name}
			set_defaults_for_summarized_view(filters, row)
			row.update(attendance)
			row.update(leave_summary)
			row.update(entry_exits_summary)

			records.append(row)
		else:
			employee_attendance = attendance_map.get(employee)
			if not employee_attendance:
				continue

			attendance_for_employee = get_attendance_status_for_detailed_view(
				employee, filters, employee_attendance, holidays
			)
			for record in attendance_for_employee:
				record.update({"employee": employee, "employee_name": details.employee_name})

			records.extend(attendance_for_employee)

	return records


def get_attendance_status_for_detailed_view(
	_employee, filters: Filters, employee_attendance: dict, holidays: list
) -> list[dict]:
	"""Return a single merged row for the employee across all shifts.

	The original HRMS implementation creates one row per shift, which causes
	Absent / Present / On Leave entries to appear on separate rows when an
	employee has attendance records filed under different shifts.  This override
	collapses all shifts into one row per employee.
	"""
	total_days = get_total_days_in_month(filters)
	row = {"shift": ""}

	for day in range(1, total_days + 1):
		status = None
		for _shift, status_dict in employee_attendance.items():
			day_status = status_dict.get(day)
			if day_status is not None:
				status = day_status
				break

		if status is None and holidays:
			status = get_holiday_status(day, holidays)

		row[cstr(day)] = status_map.get(status, "")

	return [row]
