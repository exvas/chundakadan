"""An "On Hold" status on Interview.

HR asked for it: a candidate who is neither cleared nor rejected, and whose
decision is parked. HRMS ships Pending / Under Review / Cleared / Rejected.

Safe to add. HRMS only ever branches on Cleared and Rejected:
  - `validate_submission` allows a submit only from those two, so an
    interview On Hold simply cannot be submitted, which is the point;
  - the Job Applicant status map covers only those two, so On Hold leaves
    the applicant alone;
  - the calendar's colour map is read with `.get()`, so a status it does
    not know about is merely uncoloured.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

DOCTYPE = "Interview"
FIELD = "status"
OPTIONS = "Pending\nUnder Review\nOn Hold\nCleared\nRejected"


def ensure_interview_on_hold_status(*args, **kwargs):
	"""after_migrate — keep "On Hold" on the Interview status field.

	An app update re-syncs the HRMS doctype and would drop the option, so
	this re-applies it every migrate.
	"""
	if not frappe.db.exists("DocType", DOCTYPE):
		return
	field = frappe.get_meta(DOCTYPE).get_field(FIELD)
	if not field:
		return
	if field.options == OPTIONS:
		return
	make_property_setter(
		DOCTYPE, FIELD, "options", OPTIONS, "Text", validate_fields_for_doctype=False
	)
	frappe.clear_cache(doctype=DOCTYPE)
