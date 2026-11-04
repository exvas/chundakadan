"""The Leave Application statuses the approval chain can produce.

HRMS ships Open / Approved / Rejected / Cancelled. The chain also parks a
leave at Pending and Partially Approved, and
`CustomLeaveApplication.sync_custom_status` mirrors `custom_approval_status`
straight into `status`, so the field has to accept those as well.

Three one-off patches widened it -- add_leave_status_options,
add_leave_application_pending_status, add_leave_application_partially_approved
-- and the live site has carried the wider list ever since. But `install-app`
marks patches complete without running them, so on a site created after those
patches were written (CI, a developer's bench, a restore) the field kept
HRMS' four options and the first leave the chain touched was refused with
`Status cannot be "Pending"`. One of those patches also wrote the DocField
row directly, which the next HRMS sync would undo.

The options are therefore re-applied on every migrate, and the mapping lives
here beside them: the bug was two places disagreeing about what a status can
be.

What the extra options do NOT change: HRMS creates a leave ledger entry only
for "Approved", notifies the approver only from "Open", and blocks a submit
from "Open" or "Cancelled" -- so a leave parked at Pending moves no balance.
That submit guard does not name our statuses, which is why the chain, not
HRMS, is what keeps an unapproved leave from being submitted.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

DOCTYPE = "Leave Application"
FIELD = "status"

# custom_approval_status -> status
CHAIN_STATUSES = {
	"Pending": "Pending",
	"Partially Approved": "Partially Approved",
	"Draft": "Draft",
	"Cancelled": "Cancelled",
	"Rejected": "Rejected",
	"Approved": "Approved",
}

HRMS_STATUSES = ("Open", "Approved", "Rejected", "Cancelled")


def status_options() -> str:
	"""HRMS' own statuses, then every one the chain can write."""
	options = list(HRMS_STATUSES)
	for status in CHAIN_STATUSES.values():
		if status not in options:
			options.append(status)
	return "\n".join(options)


def ensure_leave_application_statuses(*args, **kwargs):
	"""after_migrate: keep the chain's statuses on the field.

	An app update re-syncs the HRMS doctype and would drop them.
	"""
	if not frappe.db.exists("DocType", DOCTYPE):
		return
	field = frappe.get_meta(DOCTYPE).get_field(FIELD)
	if not field:
		return
	options = status_options()
	if field.options == options:
		return
	make_property_setter(DOCTYPE, FIELD, "options", options, "Text", validate_fields_for_doctype=False)
	frappe.clear_cache(doctype=DOCTYPE)
