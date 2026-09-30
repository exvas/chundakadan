# Copyright (c) 2026, Chundakadan and contributors
"""A new Customer waits for one role to clear it.

The same shape as [Item Approval]: while the feature is on, a Customer
created by anybody other than the approver is saved Pending and
**disabled**, so nobody can raise an order or an invoice against it until
it is approved. Who approves is one role named in Chundakadan Settings, so
replacing that person is a configuration change.

Deliberately a sibling of `item_approval.py` rather than a shared engine:
that module is switched on in production and its 40 tests cannot be run
from here, so it is left untouched.
"""

import json

import frappe
from frappe import _
from frappe.utils import now

SETTINGS = "Chundakadan Settings"
STATUS_FIELD = "custom_approval_status"
PENDING, APPROVED, REJECTED = "Pending", "Approved", "Rejected"

#: the only Customer fields the approver may correct before approving
EDITABLE_FIELDS = (
	"customer_name",
	"customer_group",
	"customer_type",
	"territory",
	"gstin",
	"gst_category",
	"custom_sales_person",
)

LIST_FIELDS = (
	"name",
	"customer_name",
	"customer_group",
	"customer_type",
	"territory",
	"gst_category",
	"mobile_no",
	"owner",
	"creation",
)


def _setting(fieldname):
	"""Read a Chundakadan Settings field without blowing up on a site where
	field_sales has not migrated. This runs on every Customer save."""
	try:
		meta = frappe.get_meta(SETTINGS)
	except Exception:
		return None
	if not meta.has_field(fieldname):
		return None
	return frappe.db.get_single_value(SETTINGS, fieldname)


def approval_role():
	return _setting("customer_approval_role")


def is_enabled():
	if not _setting("enable_customer_approval"):
		return False
	return bool(approval_role())


def is_approver(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	role = approval_role()
	return bool(role) and role in frappe.get_roles(user)


def approver_users():
	role = approval_role()
	if not role:
		return []
	holders = frappe.get_all(
		"Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent"
	)
	if not holders:
		return []
	return frappe.get_all(
		"User",
		filters={"name": ["in", list(set(holders))], "enabled": 1, "user_type": "System User"},
		pluck="name",
	)


def _ensure_approver():
	if not is_enabled():
		frappe.throw(_("Customer Approval is not switched on in Chundakadan Settings"))
	if not is_approver():
		raise frappe.PermissionError(_("Only the Customer approval role may do this"))


def _as_list(items):
	if isinstance(items, str):
		items = items.strip()
		items = json.loads(items) if items.startswith("[") else [items]
	return [i for i in (items or []) if i]


@frappe.whitelist()
def access():
	enabled = is_enabled()
	can_approve = enabled and is_approver()
	return {
		"enabled": enabled,
		"can_approve": can_approve,
		"role": approval_role() if enabled else None,
		"pending_count": pending_count() if can_approve else 0,
	}


def pending_count():
	if not is_enabled():
		return 0
	return frappe.db.count("Customer", {STATUS_FIELD: PENDING})


@frappe.whitelist()
def pending_customers(search=None, limit=50, start=0):
	_ensure_approver()
	or_filters = None
	if search:
		or_filters = {"name": ["like", f"%{search}%"], "customer_name": ["like", f"%{search}%"]}
	rows = frappe.get_all(
		"Customer",
		filters={STATUS_FIELD: PENDING},
		or_filters=or_filters,
		fields=list(LIST_FIELDS),
		order_by="creation desc",
		limit_page_length=int(limit or 50),
		limit_start=int(start or 0),
		ignore_permissions=True,
	)
	for row in rows:
		row["owner_name"] = frappe.db.get_value("User", row["owner"], "full_name") or row["owner"]
	return {"customers": rows, "total": pending_count()}


def _load(name):
	doc = frappe.get_doc("Customer", name)
	if doc.get(STATUS_FIELD) != PENDING:
		frappe.throw(
			_("{0} is already {1}").format(doc.name, doc.get(STATUS_FIELD) or _("not under approval"))
		)
	return doc


@frappe.whitelist()
def approve(customers, changes=None):
	"""Approve one or many Customers, enabling each one."""
	_ensure_approver()
	names = _as_list(customers)
	if not names:
		frappe.throw(_("Select at least one Customer"))
	if isinstance(changes, str):
		changes = json.loads(changes or "{}")
	changes = changes or {}
	if changes and len(names) > 1:
		frappe.throw(_("Edit one Customer at a time"))

	done = []
	for name in names:
		doc = _load(name)
		for field, value in changes.items():
			if field not in EDITABLE_FIELDS:
				frappe.throw(_("{0} cannot be changed here").format(field))
			doc.set(field, value)
		doc.set(STATUS_FIELD, APPROVED)
		doc.custom_approved_by = frappe.session.user
		doc.custom_approved_on = now()
		doc.custom_rejection_reason = None
		doc.disabled = 0
		doc.save(ignore_permissions=True)
		done.append(doc.name)
	return {"approved": done}


@frappe.whitelist()
def reject(customers, reason):
	"""Reject one or many Customers. They stay disabled and keep the reason."""
	_ensure_approver()
	names = _as_list(customers)
	if not names:
		frappe.throw(_("Select at least one Customer"))
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("A reason is needed to reject a Customer"))

	done = []
	for name in names:
		doc = _load(name)
		doc.set(STATUS_FIELD, REJECTED)
		doc.custom_rejection_reason = reason
		doc.custom_approved_by = frappe.session.user
		doc.custom_approved_on = now()
		doc.disabled = 1
		doc.save(ignore_permissions=True)
		done.append(doc.name)
	return {"rejected": done}
