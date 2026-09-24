# Copyright (c) 2026, Chundakadan and contributors
"""New Items wait for one role to clear them.

While the feature is on, an Item created by anybody other than the
approver is saved as Pending and **disabled**, so it cannot be picked on
an invoice, a purchase order or a stock entry until it is approved.

Who approves is a single role named in Chundakadan Settings (the
field_sales Single). The feature is off until that role is set and the
switch is ticked, so a site that never configures it behaves exactly as
before.

This module holds the shared rules and the whitelisted actions. The
document hooks live in `chundakadan/doc_events/item_approval.py`; the
mobile endpoints in field_sales call straight into the functions here so
there is one source of truth.
"""

import json

import frappe
from frappe import _
from frappe.utils import now

SETTINGS = "Chundakadan Settings"
STATUS_FIELD = "custom_approval_status"
PENDING, APPROVED, REJECTED = "Pending", "Approved", "Rejected"

#: the only Item fields the approver may correct before approving
EDITABLE_FIELDS = (
	"item_name",
	"item_group",
	"brand",
	"stock_uom",
	"description",
	"standard_rate",
)

#: what the pending list hands back to the desk and the mobile app
LIST_FIELDS = (
	"name",
	"item_code",
	"item_name",
	"item_group",
	"brand",
	"stock_uom",
	"standard_rate",
	"description",
	"image",
	"owner",
	"creation",
)


# --------------------------------------------------------------------------
# settings
# --------------------------------------------------------------------------


def _setting(fieldname):
	"""Read one Chundakadan Settings field.

	The Single lives in the field_sales app, so on a site where that app is
	missing or has not migrated yet the field is not there. Reading it with
	`get_single_value` would throw, and this runs on every Item save -- a
	site without the field must simply behave as if the feature is off.
	"""
	try:
		meta = frappe.get_meta(SETTINGS)
	except Exception:
		return None
	if not meta.has_field(fieldname):
		return None
	return frappe.db.get_single_value(SETTINGS, fieldname)


def approval_role():
	"""The role named in Chundakadan Settings, or None."""
	return _setting("item_approval_role")


def is_enabled():
	"""On only when the switch is ticked AND a role has been chosen."""
	if not _setting("enable_item_approval"):
		return False
	return bool(approval_role())


def is_approver(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	role = approval_role()
	return bool(role) and role in frappe.get_roles(user)


def approver_users():
	"""Enabled users holding the approval role."""
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
		frappe.throw(_("Item Approval is not switched on in Chundakadan Settings"))
	if not is_approver():
		raise frappe.PermissionError(_("Only the Item approval role may do this"))


def _as_list(items):
	"""Accept a name, a list, or the JSON string the desk/mobile posts."""
	if isinstance(items, str):
		items = items.strip()
		if items.startswith("["):
			items = json.loads(items)
		else:
			items = [items]
	return [i for i in (items or []) if i]


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------


@frappe.whitelist()
def access():
	"""What the mobile home screen needs to decide whether to show the tile."""
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
	return frappe.db.count("Item", {STATUS_FIELD: PENDING})


@frappe.whitelist()
def pending_items(search=None, limit=50, start=0):
	"""Items still waiting, newest first."""
	_ensure_approver()
	filters = {STATUS_FIELD: PENDING}
	or_filters = None
	if search:
		or_filters = {"item_code": ["like", f"%{search}%"], "item_name": ["like", f"%{search}%"]}
	rows = frappe.get_all(
		"Item",
		filters=filters,
		or_filters=or_filters,
		fields=list(LIST_FIELDS),
		order_by="creation desc",
		limit_page_length=int(limit or 50),
		limit_start=int(start or 0),
		ignore_permissions=True,
	)
	for row in rows:
		row["owner_name"] = frappe.db.get_value("User", row["owner"], "full_name") or row["owner"]
	return {"items": rows, "total": pending_count()}


# --------------------------------------------------------------------------
# acting
# --------------------------------------------------------------------------


def _load(name):
	doc = frappe.get_doc("Item", name)
	if doc.get(STATUS_FIELD) != PENDING:
		frappe.throw(
			_("{0} is already {1}").format(doc.name, doc.get(STATUS_FIELD) or _("not under approval"))
		)
	return doc


@frappe.whitelist()
def approve(items, changes=None):
	"""Approve one or many Items, enabling each one.

	`changes` corrects a single Item before it is approved; it is ignored
	for a bulk approval, where there is no one item to apply it to.
	"""
	_ensure_approver()
	names = _as_list(items)
	if not names:
		frappe.throw(_("Select at least one Item"))
	if isinstance(changes, str):
		changes = json.loads(changes or "{}")
	changes = changes or {}
	if changes and len(names) > 1:
		frappe.throw(_("Edit one Item at a time"))

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
def reject(items, reason):
	"""Reject one or many Items. They stay disabled and keep the reason."""
	_ensure_approver()
	names = _as_list(items)
	if not names:
		frappe.throw(_("Select at least one Item"))
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("A reason is needed to reject an Item"))

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
