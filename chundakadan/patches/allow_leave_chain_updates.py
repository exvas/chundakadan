import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

# The leave approval chain is updated after the application is submitted
# (approve_leave / reject_leave stamp the current row). The parent chain
# fields are already allow_on_submit, but the child row fields were not, so
# acting on an already-submitted leave failed with
# "Row #1: Not allowed to change Status after submission".
CHAIN_FIELDS = ("approver", "approver_role", "status", "approved_on", "remarks")


def execute():
	meta = frappe.get_meta("Leave Approval Detail")
	for fieldname in CHAIN_FIELDS:
		if not meta.get_field(fieldname):
			continue
		make_property_setter(
			"Leave Approval Detail",
			fieldname,
			"allow_on_submit",
			1,
			"Check",
			validate_fields_for_doctype=False,
		)
	frappe.clear_cache(doctype="Leave Approval Detail")
	frappe.clear_cache(doctype="Leave Application")
