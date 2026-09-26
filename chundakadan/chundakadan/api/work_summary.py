# Copyright (c) 2026, Chundakadan and contributors
"""Daily Work Summary — what an employee did today, and the two remarks.

The employee writes the tasks, the head of their department writes the HOD
remark, and the General Manager writes the GM remark and closes the
summary. The chain reuses the fields the leave and expense workflows
already use (`custom_approval_status`, `current_approver`,
`current_approval_index`, `approval_flow`), so the Approvals workspace and
the desk conventions carry over unchanged.

    Draft  --send_for_remarks-->  Pending (HOD)
           --add_remarks-------->  Partially Approved (GM)
           --add_remarks-------->  Approved + submitted

Either approver can hand it back with `return_for_correction`, which puts
it in Returned so the employee can fix it and send it again.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now

ROLE_GM = "GM Leave Approver"
ADMIN_ROLES = ("Administrator", "System Manager")

#: roles that see every summary, drafts included. The GM closes the chain
#: and is answerable for the whole company, so a summary sitting unsent in
#: somebody's drafts is exactly what they need to be able to see; HR
#: administers the doctype.
SEES_EVERYTHING = ("System Manager", ROLE_GM, "HR Manager")

STATUS_DRAFT = "Draft"
STATUS_PENDING = "Pending"
STATUS_PARTIAL = "Partially Approved"
STATUS_APPROVED = "Approved"
STATUS_RETURNED = "Returned"

#: which remark field belongs to which step of the chain
REMARK_FIELD = {0: "hod_remarks", 1: "gm_remarks"}
FINAL_STATES = (STATUS_APPROVED,)


# --------------------------------------------------------------------------
# who is the HOD
# --------------------------------------------------------------------------


def hod_role_for_department(department: str | None) -> str:
	"""The role that heads this department.

	Same mapping the leave workflow uses, so an employee's work summary
	goes to whoever already approves their leave.
	"""
	name = (department or "").lower()
	if "sales" in name or "marketing" in name:
		return "Sales HOD Leave Approver"
	if "accountant" in name or "account" in name or "purchase" in name:
		return "Accounts Manager Leave Approver"
	return "HR Leave Approver"


def user_for_role(role: str) -> str | None:
	"""An enabled user holding the role, preferring one with an active
	Employee record."""
	holders = frappe.get_all(
		"Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent",
		ignore_permissions=True,
	)
	holders = [h for h in holders if h not in ("Administrator", "Guest")]
	if not holders:
		return None
	enabled = frappe.get_all(
		"User", filters={"name": ["in", holders], "enabled": 1}, pluck="name"
	)
	for email in enabled:
		if frappe.db.exists("Employee", {"user_id": email, "status": "Active"}):
			return email
	return enabled[0] if enabled else None


def chain_roles(doc) -> list[str]:
	"""HOD first, then the GM who closes it."""
	hod = hod_role_for_department(doc.get("department"))
	return [hod] if hod == ROLE_GM else [hod, ROLE_GM]


# --------------------------------------------------------------------------
# permission helpers
# --------------------------------------------------------------------------


def _is_admin(user: str) -> bool:
	if user == "Administrator":
		return True
	roles = frappe.get_roles(user)
	return any(role in roles for role in ADMIN_ROLES)


def sees_everything(user: str | None = None) -> bool:
	"""The GM and HR see every summary, including drafts nobody has sent."""
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	roles = frappe.get_roles(user)
	return any(role in roles for role in SEES_EVERYTHING)


def employee_user(doc) -> str | None:
	if not doc.get("employee"):
		return None
	return frappe.db.get_value("Employee", doc.employee, "user_id")


def is_owner(doc, user: str | None = None) -> bool:
	user = user or frappe.session.user
	return user == doc.owner or user == employee_user(doc)


def can_act_now(doc, user: str | None = None) -> bool:
	"""True when it is this user's turn in the chain."""
	user = user or frappe.session.user
	if _is_admin(user):
		return True
	if doc.get("current_approver") == user:
		return True
	idx = int(doc.get("current_approval_index") or 0)
	flow = doc.get("approval_flow") or []
	if 0 <= idx < len(flow):
		row = flow[idx]
		if row.approver == user:
			return True
		if row.approver_role and row.approver_role in frappe.get_roles(user):
			return True
	return False


def _ensure_can_act(doc):
	if not can_act_now(doc):
		raise frappe.PermissionError(
			_("It is not your turn on {0}").format(doc.name)
		)


# --------------------------------------------------------------------------
# document hooks
# --------------------------------------------------------------------------


def validate(doc, method=None):
	_default_employee(doc)
	_one_per_day(doc)
	_guard_remarks(doc)
	_guard_direct_submit(doc)


def _default_employee(doc):
	if not doc.employee:
		employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"})
		if employee:
			doc.employee = employee
	if doc.employee and not doc.department:
		doc.department = frappe.db.get_value("Employee", doc.employee, "department")
	if not doc.company and doc.employee:
		doc.company = frappe.db.get_value("Employee", doc.employee, "company")
	if not doc.custom_approval_status:
		doc.custom_approval_status = STATUS_DRAFT


def _one_per_day(doc):
	"""One summary per employee per day — otherwise the day's record is
	split across documents and nobody can tell what was actually done."""
	if not (doc.employee and doc.work_date):
		return
	clash = frappe.db.exists(
		"Daily Work Summary",
		{
			"employee": doc.employee,
			"work_date": doc.work_date,
			"docstatus": ["<", 2],
			"name": ["!=", doc.name],
		},
	)
	if clash:
		frappe.throw(
			_("{0} already has a work summary for {1}: {2}").format(
				doc.employee_name or doc.employee, frappe.format(doc.work_date, {"fieldtype": "Date"}), clash
			)
		)


def _guard_remarks(doc):
	"""A remark belongs to the step that writes it.

	Without this the employee could type the HOD's remark themselves, and
	the HOD could write the GM's.
	"""
	before = doc.get_doc_before_save()
	if not before or _is_admin(frappe.session.user):
		return
	idx = int(doc.get("current_approval_index") or 0)
	mine = REMARK_FIELD.get(idx) if doc.custom_approval_status in (STATUS_PENDING, STATUS_PARTIAL) else None
	for step, field in REMARK_FIELD.items():
		if doc.get(field) == before.get(field):
			continue
		if field != mine or not can_act_now(doc):
			frappe.throw(
				_("Only the approver at that step may write {0}").format(
					doc.meta.get_label(field)
				),
				frappe.PermissionError,
			)


def _guard_direct_submit(doc):
	"""The Submit button must not skip the chain — the GM closes it through
	`add_remarks`, which sets Approved first."""
	if int(doc.get("docstatus") or 0) == 1 and doc.custom_approval_status != STATUS_APPROVED:
		frappe.throw(
			_("A work summary is closed by the General Manager, not by Submit. Waiting on: {0}").format(
				doc.get("current_approver") or "—"
			)
		)


# --------------------------------------------------------------------------
# the chain
# --------------------------------------------------------------------------


def _build_flow(doc):
	doc.set("approval_flow", [])
	for role in chain_roles(doc):
		approver = user_for_role(role)
		if not approver:
			frappe.throw(
				_("No active user holds the role '{0}', so this summary cannot be sent.").format(role)
			)
		doc.append("approval_flow", {"approver": approver, "approver_role": role, "status": "Pending"})
	doc.current_approval_index = 0
	doc.current_approver = doc.approval_flow[0].approver
	doc.custom_approval_status = STATUS_PENDING
	doc.return_reason = None


@frappe.whitelist()
def send_for_remarks(docname: str):
	"""The employee sends the day's summary to their HOD."""
	doc = frappe.get_doc("Daily Work Summary", docname)
	if not (is_owner(doc) or _is_admin(frappe.session.user)):
		raise frappe.PermissionError(_("Only {0} can send this summary").format(doc.employee_name))
	if doc.custom_approval_status not in (STATUS_DRAFT, STATUS_RETURNED):
		frappe.throw(_("This summary has already been sent."))
	if not doc.get("tasks"):
		frappe.throw(_("Add at least one task before sending."))
	_build_flow(doc)
	doc.save(ignore_permissions=True)
	_notify(doc.current_approver, _("Work summary to review"),
	        "{0} — {1}".format(doc.employee_name or doc.employee, frappe.format(doc.work_date, {"fieldtype": "Date"})),
	        doc.name)
	return {"status": doc.custom_approval_status, "current_approver": doc.current_approver}


@frappe.whitelist()
def add_remarks(docname: str, remarks: str | None = None):
	"""The approver at the current step writes their remark and passes it on.

	The last step (the GM) closes the summary, which submits it.
	"""
	doc = frappe.get_doc("Daily Work Summary", docname)
	if doc.custom_approval_status in FINAL_STATES:
		frappe.throw(_("This summary is already closed."))
	_ensure_can_act(doc)

	idx = int(doc.current_approval_index or 0)
	flow = doc.get("approval_flow") or []
	if not flow or idx >= len(flow):
		frappe.throw(_("Approval chain is not set up."))

	field = REMARK_FIELD.get(idx)
	remarks = (remarks or "").strip()
	if not remarks:
		frappe.throw(_("Write a remark before passing this on."))

	row = flow[idx]
	row.status = "Approved"
	row.approved_on = now()
	row.remarks = remarks
	if row.approver != frappe.session.user and not _is_admin(frappe.session.user):
		row.approver = frappe.session.user

	original = frappe.session.user
	try:
		frappe.set_user("Administrator")
		if field:
			doc.set(field, remarks)
		if idx + 1 >= len(flow):
			doc.custom_approval_status = STATUS_APPROVED
			doc.current_approver = None
			doc.submit()
			target = employee_user(doc)
			title, body = _("Work summary closed"), _("The GM has closed your summary for {0}").format(doc.work_date)
		else:
			doc.current_approval_index = idx + 1
			doc.current_approver = flow[idx + 1].approver
			doc.custom_approval_status = STATUS_PARTIAL
			doc.save(ignore_permissions=True)
			target = doc.current_approver
			title, body = _("Work summary to review"), "{0} — {1}".format(
				doc.employee_name or doc.employee, doc.work_date
			)
	finally:
		frappe.set_user(original)

	_notify(target, title, body, doc.name)
	return {"status": doc.custom_approval_status, "current_approver": doc.current_approver}


@frappe.whitelist()
def return_for_correction(docname: str, reason: str | None = None):
	"""Hand the summary back so the employee can fix it and send it again."""
	doc = frappe.get_doc("Daily Work Summary", docname)
	if doc.custom_approval_status in FINAL_STATES or int(doc.docstatus or 0) == 1:
		frappe.throw(_("This summary is already closed."))
	_ensure_can_act(doc)
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Say what needs correcting."))

	original = frappe.session.user
	try:
		frappe.set_user("Administrator")
		doc.custom_approval_status = STATUS_RETURNED
		doc.return_reason = reason
		doc.current_approver = employee_user(doc)
		doc.current_approval_index = 0
		doc.set("approval_flow", [])
		doc.save(ignore_permissions=True)
	finally:
		frappe.set_user(original)

	_notify(employee_user(doc), _("Work summary returned"), reason, doc.name)
	return {"status": doc.custom_approval_status, "reason": reason}


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------


@frappe.whitelist()
def waiting_on_me():
	"""Summaries at this user's step — the desk card and the mobile team tab."""
	user = frappe.session.user
	roles = frappe.get_roles(user)
	names = frappe.get_all(
		"Daily Work Summary",
		filters={"docstatus": 0, "custom_approval_status": ["in", [STATUS_PENDING, STATUS_PARTIAL]]},
		fields=["name", "employee", "employee_name", "work_date", "department",
		        "custom_approval_status", "current_approver", "current_approval_index"],
		order_by="work_date desc",
		ignore_permissions=True,
	)
	mine = []
	for row in names:
		if row["current_approver"] == user:
			mine.append(row)
			continue
		# Every later row is still Pending too, so the step has to be picked
		# by index -- otherwise the GM sees summaries still sitting with the
		# HOD. Child table idx is 1-based.
		step_role = frappe.db.get_value(
			"Chundakadan Approval Detail",
			{
				"parent": row["name"],
				"parenttype": "Daily Work Summary",
				"idx": int(row["current_approval_index"] or 0) + 1,
			},
			"approver_role",
		)
		if step_role and step_role in roles:
			mine.append(row)
	return mine


def _notify(user, title, body, docname):
	if not user:
		return
	try:
		from chundakadan.utils import push

		push.send_to_users([user], title, body, {"route": "/work_summary", "name": docname})
	except Exception:
		frappe.log_error("chundakadan.work_summary.notify", frappe.get_traceback())


# --------------------------------------------------------------------------
# row-level visibility
# --------------------------------------------------------------------------


def get_permission_query_conditions(user=None):
	"""An employee sees their own; an approver sees what is or was theirs."""
	user = user or frappe.session.user
	if sees_everything(user):
		return ""
	safe = frappe.db.escape(user)
	clauses = [
		f"`tabDaily Work Summary`.owner = {safe}",
		f"`tabDaily Work Summary`.current_approver = {safe}",
		f"`tabDaily Work Summary`.employee in "
		f"(select name from `tabEmployee` where user_id = {safe})",
		f"exists (select 1 from `tabChundakadan Approval Detail` af "
		f"where af.parent = `tabDaily Work Summary`.name and af.approver = {safe})",
	]
	roles = [r for r in frappe.get_roles(user) if r.endswith("Leave Approver")]
	if roles:
		role_list = ", ".join(frappe.db.escape(r) for r in roles)
		clauses.append(
			f"exists (select 1 from `tabChundakadan Approval Detail` af "
			f"where af.parent = `tabDaily Work Summary`.name and af.approver_role in ({role_list}))"
		)
	return "(" + " or ".join(clauses) + ")"


def has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if sees_everything(user):
		return True
	if is_owner(doc, user):
		return True
	if can_act_now(doc, user):
		return True
	return any(row.approver == user for row in (doc.get("approval_flow") or []))


# --------------------------------------------------------------------------
# who has not sent today's summary
# --------------------------------------------------------------------------


def _setting(fieldname):
	"""Read a Chundakadan Settings field without blowing up on a site where
	field_sales has not migrated. Same guard as the Item approval feature."""
	try:
		meta = frappe.get_meta("Chundakadan Settings")
	except Exception:
		return None
	if not meta.has_field(fieldname):
		return None
	return frappe.db.get_single_value("Chundakadan Settings", fieldname)


def _is_holiday(employee: str, day) -> bool:
	"""A day off is not a missing summary."""
	from frappe.utils import getdate

	holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")
	if not holiday_list:
		company = frappe.db.get_value("Employee", employee, "company")
		holiday_list = frappe.db.get_value("Company", company, "default_holiday_list")
	if not holiday_list:
		return False
	return bool(
		frappe.db.exists("Holiday", {"parent": holiday_list, "holiday_date": getdate(day)})
	)


def _on_leave(employee: str, day) -> bool:
	return bool(
		frappe.db.exists(
			"Leave Application",
			{
				"employee": employee,
				"docstatus": 1,
				"status": "Approved",
				"from_date": ["<=", day],
				"to_date": [">=", day],
			},
		)
	)


def not_submitted(day=None, department: str | None = None, company: str | None = None):
	"""Active employees with no summary sent for `day`.

	A draft nobody sent counts as not submitted -- the point is whether the
	HOD received it. People on a holiday or on approved leave are left out.
	"""
	from frappe.utils import today

	day = day or today()
	filters = {"status": "Active"}
	if department:
		filters["department"] = department
	if company:
		filters["company"] = company
	employees = frappe.get_all(
		"Employee", filters=filters, fields=["name", "employee_name", "department", "user_id", "company"]
	)
	sent = set(
		frappe.get_all(
			"Daily Work Summary",
			filters={
				"work_date": day,
				"docstatus": ["<", 2],
				"custom_approval_status": ["not in", [STATUS_DRAFT, STATUS_RETURNED]],
			},
			pluck="employee",
		)
	)
	missing = []
	for employee in employees:
		if employee.name in sent:
			continue
		if _is_holiday(employee.name, day) or _on_leave(employee.name, day):
			continue
		missing.append(employee)
	return missing


def send_submission_reminders():
	"""Hourly cron. Pushes once, in the hour the configured time falls in,
	to everyone who has not sent the day's summary."""
	from frappe.utils import now_datetime, today

	if not _setting("enable_work_summary_reminder"):
		return
	target = _setting("work_summary_reminder_time")
	if not target:
		return
	hour = int(str(target).split(":")[0])
	if now_datetime().hour != hour:
		return

	users = [e.user_id for e in not_submitted(today()) if e.user_id]
	if not users:
		return
	try:
		from chundakadan.utils import push

		push.send_to_users(
			users,
			_("Daily work summary"),
			_("Please send today's work summary."),
			{"route": "/work_summary"},
		)
	except Exception:
		frappe.log_error("chundakadan.work_summary.reminders", frappe.get_traceback())
