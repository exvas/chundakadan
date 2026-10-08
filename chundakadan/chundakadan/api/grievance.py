# Copyright (c) 2026, Chundakadan and contributors
"""Raising a grievance from the phone, and keeping it private.

An employee picks one of the predefined Grievance Types, writes what
happened, and that is the whole form -- HRMS asks for more, so the rest
is filled in here rather than put in front of somebody who is already
upset.

Who may read one is the point of the feature. The GM and the HR Manager
read every grievance; the person who raised it reads their own; nobody
else sees that one exists.

**HR User is deliberately not on that list.** Fourteen people hold it,
most of them ordinary staff -- a grievance about a colleague would land
in front of the colleague.
"""

import frappe
from frappe import _
from frappe.utils import today

DOCTYPE = "Employee Grievance"
ROLE_GM = "GM Leave Approver"

#: the roles that read every grievance -- see the module docstring on why
#: HR User is not one of them
SEES_EVERYTHING = ("System Manager", ROLE_GM, "HR Manager")

OPEN = "Open"


def ensure_grievance_permissions(*args, **kwargs):
	"""after_migrate — the GM reads grievances in their own right.

	`GM Leave Approver` is not on the doctype's permission list, so without
	this the GM only sees a grievance because they also happen to hold
	HR Manager. Take that role away one day and the grievances would go
	quiet, which is the one thing this feature must not do.
	"""
	if not frappe.db.exists("DocType", DOCTYPE):
		return
	if frappe.db.exists("Custom DocPerm", {"parent": DOCTYPE, "role": ROLE_GM, "permlevel": 0}):
		return
	from frappe.permissions import add_permission, update_permission_property

	add_permission(DOCTYPE, ROLE_GM, 0)
	for ptype in ("read", "write", "report", "export", "print", "email", "share"):
		update_permission_property(DOCTYPE, ROLE_GM, 0, ptype, 1)


def caller_employee(user: str | None = None) -> str | None:
	user = user or frappe.session.user
	return frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")


def sees_everything(user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	roles = frappe.get_roles(user)
	return any(role in roles for role in SEES_EVERYTHING)


@frappe.whitelist()
def grievance_types() -> list[str]:
	"""The predefined list the employee picks from."""
	return frappe.db.get_all("Grievance Type", pluck="name", order_by="name")


@frappe.whitelist()
def raise_grievance(grievance_type: str | None = None, description: str | None = None):
	"""Record a grievance for the signed-in employee.

	Only the type and the description are asked for. HRMS also demands a
	subject and something for the grievance to be "against"; neither adds
	anything here, so the type stands as the subject and the company is
	the party.
	"""
	employee = caller_employee()
	if not employee:
		frappe.throw(_("No active Employee is linked to your account."))

	grievance_type = (grievance_type or "").strip()
	description = (description or "").strip()
	if not grievance_type:
		frappe.throw(_("Choose a grievance type."))
	if not frappe.db.exists("Grievance Type", grievance_type):
		frappe.throw(_("{0} is not a grievance type.").format(grievance_type))
	if not description:
		frappe.throw(_("Describe the grievance."))

	company = frappe.db.get_value("Employee", employee, "company")
	doc = frappe.get_doc({
		"doctype": DOCTYPE,
		"raised_by": employee,
		"grievance_type": grievance_type,
		"subject": grievance_type,
		"description": description,
		"date": today(),
		"status": OPEN,
		"grievance_against_party": "Company",
		"grievance_against": company,
	})
	doc.insert(ignore_permissions=True)
	_notify_the_people_who_handle_it(doc)
	return {"name": doc.name, "status": doc.status, "date": str(doc.date)}


@frappe.whitelist()
def my_grievances(limit: int = 20) -> list[dict]:
	"""What the signed-in employee has raised, newest first."""
	employee = caller_employee()
	if not employee:
		return []
	return frappe.db.get_all(
		DOCTYPE,
		filters={"raised_by": employee},
		fields=["name", "grievance_type", "description", "status", "date", "docstatus"],
		order_by="date desc, creation desc",
		limit=int(limit or 20),
	)


def _notify_the_people_who_handle_it(doc):
	"""A grievance nobody is told about is a grievance nobody answers."""
	seen = set()
	for role in (ROLE_GM, "HR Manager"):
		for user in frappe.db.get_all(
			"Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent"
		):
			if user in seen or not frappe.db.get_value("User", user, "enabled"):
				continue
			seen.add(user)
			try:
				frappe.get_doc({
					"doctype": "Notification Log",
					"for_user": user,
					"type": "Alert",
					"subject": _("Grievance raised: {0}").format(doc.grievance_type),
					"email_content": doc.description,
					"document_type": DOCTYPE,
					"document_name": doc.name,
				}).insert(ignore_permissions=True)
			except Exception:
				frappe.log_error(title="grievance notification", message=frappe.get_traceback())


# --------------------------------------------------------------------------
# who may read one
# --------------------------------------------------------------------------


def get_permission_query_conditions(user=None):
	"""List view: the GM and HR see everything, everyone else their own."""
	user = user or frappe.session.user
	if sees_everything(user):
		return ""
	employee = caller_employee(user)
	if not employee:
		# no employee record means nothing of their own to see
		return "1 = 0"
	return f"`tabEmployee Grievance`.raised_by = {frappe.db.escape(employee)}"


def has_permission(doc, ptype=None, user=None):
	"""One document: same rule as the list."""
	user = user or frappe.session.user
	if sees_everything(user):
		return True
	return doc.get("raised_by") == caller_employee(user)
