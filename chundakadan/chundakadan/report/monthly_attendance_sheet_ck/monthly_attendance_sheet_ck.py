# Copyright (c) 2026, Ashkar and contributors
# For license information, please see license.txt
#
# Monthly Attendance Sheet (CK) — chundakadan's own version of the HRMS report.
# Single row per employee: all shifts merged into one row.

import frappe
from frappe.utils import cstr, getdate

import hrms.hr.report.monthly_attendance_sheet.monthly_attendance_sheet as _mas


def execute(filters=None):
	filters = frappe._dict(filters or {})

	# When "Date Range" is selected, derive month and year from from_date
	if filters.get("filter_based_on") == "Date Range" and filters.get("from_date"):
		d = getdate(filters.from_date)
		filters.month = str(d.month)
		filters.year = str(d.year)

	# Patch HRMS's helper with our single-row version, then delegate entirely to
	# HRMS's execute so it handles all filter setup and query building correctly
	# regardless of the installed HRMS version.
	_mas.get_attendance_status_for_detailed_view = _single_row_attendance_status
	return _mas.execute(filters)


def _single_row_attendance_status(_employee, filters, employee_attendance, holidays):
	"""Merge all shift rows into one row per employee.

	HRMS creates one row per shift, causing Absent / Present / On Leave to
	appear on separate rows when attendance is recorded under different shifts.
	This collapses all shifts into a single row.
	"""
	total_days = _mas.get_total_days_in_month(filters)
	row = {"shift": ""}

	for day in range(1, total_days + 1):
		status = None
		for _shift, status_dict in employee_attendance.items():
			day_status = status_dict.get(day)
			if day_status is not None:
				status = day_status
				break

		if status is None and holidays:
			status = _mas.get_holiday_status(day, holidays)

		row[cstr(day)] = _mas.status_map.get(status, "")

	return [row]
