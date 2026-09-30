# Copyright (c) 2026, Chundakadan and contributors
"""Document hooks that hold a new Customer until the approver clears it.

The rules live in `chundakadan/chundakadan/api/customer_approval.py`; this
file wires them to Customer's save cycle and creates the custom fields.
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import now

from chundakadan.chundakadan.api.customer_approval import (
	APPROVED,
	PENDING,
	STATUS_FIELD,
	approver_users,
	is_approver,
	is_enabled,
)

GUARDED_FIELDS = (
	STATUS_FIELD,
	"custom_approved_by",
	"custom_approved_on",
	"custom_rejection_reason",
)

CUSTOM_FIELDS = {
	"Customer": [
		{
			"fieldname": "custom_approval_section",
			"label": "Approval",
			"fieldtype": "Section Break",
			"insert_after": "disabled",
			"collapsible": 1,
		},
		{
			"fieldname": STATUS_FIELD,
			"label": "Approval Status",
			"fieldtype": "Select",
			"options": "\nPending\nApproved\nRejected",
			"insert_after": "custom_approval_section",
			"read_only": 1,
			"in_standard_filter": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "custom_approved_by",
			"label": "Approved By",
			"fieldtype": "Link",
			"options": "User",
			"insert_after": STATUS_FIELD,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "custom_approval_column",
			"fieldtype": "Column Break",
			"insert_after": "custom_approved_by",
		},
		{
			"fieldname": "custom_approved_on",
			"label": "Approved On",
			"fieldtype": "Datetime",
			"insert_after": "custom_approval_column",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "custom_rejection_reason",
			"label": "Rejection Reason",
			"fieldtype": "Small Text",
			"insert_after": "custom_approved_on",
			"read_only": 1,
			"no_copy": 1,
			"depends_on": f"eval:doc.{STATUS_FIELD}=='Rejected'",
		},
	]
}


def ensure_customer_approval_fields(*args, **kwargs):
	"""after_migrate — keep the Customer approval fields on every site."""
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)


def _skip():
	"""Imports, installs, migrations and patches never go through approval.

	A 2,000-row customer import would otherwise land as 2,000 disabled
	Pending customers -- which is exactly what the 2026-09 re-import was.
	"""
	return bool(
		frappe.flags.in_import
		or frappe.flags.in_migrate
		or frappe.flags.in_install
		or frappe.flags.in_patch
	)


def hold_new_customer(doc, method=None):
	"""before_insert — Pending and disabled unless the approver made it."""
	if not is_enabled() or _skip():
		return
	if is_approver():
		doc.set(STATUS_FIELD, APPROVED)
		doc.custom_approved_by = frappe.session.user
		doc.custom_approved_on = now()
		return
	doc.set(STATUS_FIELD, PENDING)
	doc.custom_approved_by = None
	doc.custom_approved_on = None
	doc.custom_rejection_reason = None
	doc.disabled = 1


def guard_approval_fields(doc, method=None):
	"""validate — nobody but the approver moves the status or re-enables a
	held Customer. Without this whoever created it could simply untick
	Disabled and the approval would mean nothing."""
	if not is_enabled() or _skip() or doc.is_new():
		return
	if is_approver():
		return
	before = doc.get_doc_before_save()
	if not before:
		return
	for field in GUARDED_FIELDS:
		if doc.get(field) != before.get(field):
			frappe.throw(
				_("Only the Customer approval role may change {0}").format(
					frappe.get_meta("Customer").get_label(field)
				),
				frappe.PermissionError,
			)
	if before.get(STATUS_FIELD) in (PENDING, "Rejected") and not doc.disabled:
		frappe.throw(
			_("{0} is not approved yet, so it cannot be enabled").format(doc.name),
			frappe.PermissionError,
		)


def notify_approvers(doc, method=None):
	"""after_insert — tell the approvers a new Customer is waiting."""
	if not is_enabled() or _skip():
		return
	if doc.get(STATUS_FIELD) != PENDING:
		return
	users = approver_users()
	if not users:
		return
	from chundakadan.utils import push

	try:
		push.send_to_users(
			users,
			_("New Customer needs approval"),
			"{0} — {1}".format(doc.name, doc.customer_name or ""),
			{"route": "/customer_approvals", "name": doc.name},
		)
	except Exception:
		frappe.log_error("chundakadan.customer_approval.notify", frappe.get_traceback())
