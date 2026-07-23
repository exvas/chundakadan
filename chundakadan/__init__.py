__version__ = "0.0.1"

import frappe

# Monkey patch standard report with custom implementation
try:
	import hrms.hr.report.employee_leave_balance.employee_leave_balance as standard_report
	from chundakadan.overrides import employee_leave_balance as custom_report
	
	standard_report.execute = custom_report.execute
except ImportError:
	pass

# Self-heal corrupt cached sessions ("User None is disabled") — see overrides/session_healing.py
try:
	from chundakadan.overrides import session_healing

	session_healing.install()
except ImportError:
	pass
