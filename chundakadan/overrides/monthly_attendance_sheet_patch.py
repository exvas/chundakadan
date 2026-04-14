"""
Patches the HRMS Monthly Attendance Sheet report so that each employee
appears in a single row (all shifts merged), instead of one row per shift.
"""

from frappe.utils import cstr

_patched = False


def apply_patch():
	global _patched
	if _patched:
		return
	try:
		import hrms.hr.report.monthly_attendance_sheet.monthly_attendance_sheet as mas

		mas.get_attendance_status_for_detailed_view = _single_row_attendance_status
		_patched = True
	except ImportError:
		pass


def _single_row_attendance_status(employee, filters, employee_attendance, holidays):
	"""Returns a single merged row for the employee across all shifts.

	Original behaviour created one row per shift which led to separate rows for
	Absent, Present, and On Leave when an employee had attendance records under
	different shifts.  This override collapses all shifts into one row.
	"""
	from hrms.hr.report.monthly_attendance_sheet.monthly_attendance_sheet import (
		get_holiday_status,
		get_total_days_in_month,
		status_map,
	)

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
