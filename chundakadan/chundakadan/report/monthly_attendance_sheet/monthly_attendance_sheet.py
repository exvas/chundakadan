# Copyright (c) 2026, Ashkar and contributors
# For license information, please see license.txt
#
# Overrides HRMS Monthly Attendance Sheet to collapse all shifts into a single
# row per employee instead of one row per shift.

from frappe.utils import cstr

import hrms.hr.report.monthly_attendance_sheet.monthly_attendance_sheet as _mas


def _single_row_attendance_status(_employee, filters, employee_attendance, holidays):
	"""Merge all shift rows into one row per employee.

	The original HRMS implementation creates a separate row for each shift an
	employee has attendance records in, which causes Absent/Present/On Leave
	entries to appear as multiple rows.  This override iterates over all shifts
	and picks the status for each calendar day, returning a single row.
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


# Patch the hrms module at import time so the full call chain
# (execute → get_data → get_rows → get_attendance_status_for_detailed_view)
# uses our single-row implementation.
_mas.get_attendance_status_for_detailed_view = _single_row_attendance_status

# Re-export the hrms entry points so the report framework finds them here.
execute = _mas.execute
get_attendance_years = _mas.get_attendance_years
