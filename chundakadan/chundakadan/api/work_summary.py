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

#: which remark field belongs to which step of the chain.
#: 2026-10-01: the chain is the GM alone. The HOD step was dropped on the
#: user's instruction -- the HOD still follows their department and can
#: comment, but nothing waits on them. `hod_remarks` is retired: the ones
#: already written stay readable, nobody can write a new one.
REMARK_FIELD = {0: "gm_remarks"}
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
	"""The GM alone.

	Until 2026-10-01 this was HOD then GM. The user asked for GM approval
	only: a summary should not sit waiting on a department head. The HOD
	keeps the visibility and the comments (`oversees_departments`,
	`add_comment`) -- they follow the team without blocking it.
	"""
	return [ROLE_GM]


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


def departments_for_role(role: str) -> list[str]:
	"""Every department whose work summaries this HOD role oversees.

	Built from the same matching `hod_role_for_department` uses, so a
	department can never be routed to one HOD and shown to another.
	"""
	return [
		d for d in frappe.get_all("Department", pluck="name")
		if hod_role_for_department(d) == role
	]


def oversees_departments(user: str | None = None) -> list[str]:
	"""Departments this user is the HOD of, by role.

	The Sales HOD asked to follow the whole sales team's summaries, not only
	the ones parked at their own step, so they see their departments outright
	-- drafts included, the same as the GM.
	"""
	user = user or frappe.session.user
	roles = frappe.get_roles(user)
	departments = []
	for role in ("Sales HOD Leave Approver", "Accounts Manager Leave Approver"):
		if role in roles:
			departments.extend(departments_for_role(role))
	return sorted(set(departments))


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
	_auto_send(doc)


def _auto_send(doc):
	"""A saved summary with work in it is in front of the GM. Full stop.

	There used to be a separate "Send for Remarks" step. Nobody pressed it,
	so every summary sat in Draft and the GM -- the only approver -- opened
	the list to a column of "Draft" with nothing to act on. With a one-step
	chain that step bought nothing, so writing the day's work is the sending.

	A summary with no task yet stays a draft: there is nothing to approve.
	"""
	if int(doc.get("docstatus") or 0) != 0:
		return
	if doc.flags.get("returning"):
		# the save that hands it back must not send it straight out again
		return
	if doc.custom_approval_status == STATUS_RETURNED:
		# a returned summary goes back only when the employee has worked on
		# it; the GM reading it should not push it on for them
		if not is_owner(doc):
			return
	elif doc.custom_approval_status != STATUS_DRAFT:
		return
	if not doc.get("tasks"):
		return
	# never block a save over the chain: if the GM role has no active holder,
	# the summary simply stays a draft until it does.
	try:
		_build_flow(doc)
	except frappe.ValidationError:
		doc.custom_approval_status = STATUS_DRAFT


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
	# the employee sends their own; the GM and HR can also push one that is
	# stuck in somebody's drafts, which is the whole point of them seeing drafts
	if not (is_owner(doc) or sees_everything()):
		raise frappe.PermissionError(_("Only {0} can send this summary").format(doc.employee_name))
	if doc.custom_approval_status in FINAL_STATES:
		frappe.throw(_("This summary is already closed."))
	if doc.custom_approval_status not in (STATUS_DRAFT, STATUS_RETURNED):
		# saving already sent it; the mobile app still calls this, so say yes
		return {"status": doc.custom_approval_status, "current_approver": doc.current_approver}
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
		doc.flags.returning = True
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
def team_summaries(scope: str = "waiting", limit: int = 50):
	"""What an HOD follows: their step's queue, or the whole team.

	`scope="all"` is the sales manager's ask -- every summary from the
	departments they head, drafts included, not only what is parked with
	them right now.
	"""
	if scope != "all":
		return waiting_on_me()
	departments = oversees_departments()
	if not departments and not sees_everything():
		return []
	filters = {"docstatus": ["<", 2]}
	if departments and not sees_everything():
		filters["department"] = ["in", departments]
	return frappe.get_all(
		"Daily Work Summary",
		filters=filters,
		fields=["name", "employee", "employee_name", "work_date", "department",
		        "custom_approval_status", "current_approver", "current_approval_index"],
		order_by="work_date desc, modified desc",
		limit_page_length=int(limit or 50),
		ignore_permissions=True,
	)


@frappe.whitelist()
def add_comment(docname: str, comment: str | None = None):
	"""Leave a note on a summary without touching the chain.

	The HOD remark is part of the approval and belongs to that one step; a
	manager following the team needs to say something on any summary, at any
	time, without signing anything.
	"""
	doc = frappe.get_doc("Daily Work Summary", docname)
	if not (sees_everything() or can_act_now(doc) or is_owner(doc)
	        or (doc.department and doc.department in oversees_departments())):
		raise frappe.PermissionError(_("You cannot comment on {0}").format(docname))
	comment = (comment or "").strip()
	if not comment:
		frappe.throw(_("Write something before posting."))
	entry = frappe.get_doc({
		"doctype": "Comment",
		"comment_type": "Comment",
		"reference_doctype": "Daily Work Summary",
		"reference_name": docname,
		"content": comment,
		"comment_email": frappe.session.user,
		"comment_by": frappe.db.get_value("User", frappe.session.user, "full_name"),
	})
	entry.flags.ignore_permissions = True
	entry.insert()
	_notify(employee_user(doc), _("Comment on your work summary"), comment, docname)
	return {"comment": entry.name}


@frappe.whitelist()
def comments(docname: str):
	"""Notes left on a summary, oldest first."""
	doc = frappe.get_doc("Daily Work Summary", docname)
	if not has_permission(doc):
		raise frappe.PermissionError(_("You cannot read {0}").format(docname))
	return frappe.get_all(
		"Comment",
		filters={"reference_doctype": "Daily Work Summary", "reference_name": docname,
		         "comment_type": "Comment"},
		fields=["name", "comment_by", "comment_email", "content", "creation"],
		order_by="creation asc",
	)


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
	departments = oversees_departments(user)
	if departments:
		dept_list = ", ".join(frappe.db.escape(d) for d in departments)
		clauses.append(f"`tabDaily Work Summary`.department in ({dept_list})")
	return "(" + " or ".join(clauses) + ")"


def has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if sees_everything(user):
		return True
	if is_owner(doc, user):
		return True
	if can_act_now(doc, user):
		return True
	if doc.get("department") and doc.get("department") in oversees_departments(user):
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
