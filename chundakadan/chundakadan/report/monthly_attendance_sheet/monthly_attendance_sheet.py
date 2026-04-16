# Copyright (c) 2026, Ashkar and contributors
# For license information, please see license.txt
#
# Overrides the HRMS Monthly Attendance Sheet so each employee appears in a
# single row instead of one row per shift.
#
# Strategy: patch the one helper function we care about on the HRMS module
# right before delegating to HRMS's own execute.  This way HRMS handles all
# filter validation and query setup regardless of its version.

from frappe.utils import cstr

import hrms.hr.report.monthly_attendance_sheet.monthly_attendance_sheet as _mas


def execute(filters=None):
	# Patch HRMS's helper with our single-row version, then let HRMS run.
	# Re-applying on every call is intentional and virtually free – it ensures
	# the patch is always in place even after a gunicorn worker restart.
	_mas.get_attendance_status_for_detailed_view = _single_row_attendance_status
	return _mas.execute(filters)


def _single_row_attendance_status(_employee, filters, employee_attendance, holidays):
	"""Merge all shift rows into one row per employee.

	The original HRMS implementation creates one row per shift, which causes
	Absent / Present / On Leave entries to appear on separate rows when an
	employee has attendance records filed under different shifts.
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
