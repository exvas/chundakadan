# Copyright (c) 2026, Ashkar and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def _caller_can_act_on(doc):
    """Return True if the calling user is authorised to approve / reject
    the current step of `doc`.

    Originally the gate was a strict `current_user == doc.current_approver`
    check. That broke whenever `get_approver_by_role(...)` resolved a step
    to user A while user B (who also holds the role) wanted to act —
    e.g. Bindu (binduudayan334@gmail.com) couldn't approve a leave where
    the chain resolved the GM step to Najeeb (chundakadangm@gmail.com),
    even though Bindu also holds the "GM Leave Approver" role.

    Widened policy — caller is authorised if ANY of:
      1. caller is Administrator
      2. caller == doc.current_approver (the resolved user)
      3. caller == doc.leave_approver (the standard ERPNext designated
         approver field; set per-doc by HR)
      4. caller has the role attached to the CURRENT step
         (approval_flow[current_approval_index].approver_role)
    """
    user = frappe.session.user
    if user == "Administrator":
        return True
    if doc.current_approver and user == doc.current_approver:
        return True
    if doc.get("leave_approver") and user == doc.leave_approver:
        return True
    idx = doc.current_approval_index or 0
    if doc.approval_flow and 0 <= idx < len(doc.approval_flow):
        step_role = doc.approval_flow[idx].approver_role
        if step_role and step_role in frappe.get_roles(user):
            return True
    return False


def get_approver_by_role(role):
    """
    Helper function to dynamically fetch the approver user based on the custom role.
    It resolves the enabled User assigned to the specified Role.
    If multiple users exist, it prefers the one linked to an active Employee record.
    
    Args:
        role (str): The custom role name (e.g. 'ASM Leave Approver')
        
    Returns:
        str: Email (user_id) of the matched approver user, or None
    """
    users = frappe.get_all(
        "Has Role",
        filters={"role": role},
        fields=["parent"]
    )
    if not users:
        return None
        
    # 1. Prefer active employees with enabled users
    for u in users:
        user_id = u.parent
        if frappe.db.get_value("User", user_id, "enabled"):
            # Check if user is linked to an active employee
            employee_exists = frappe.db.exists(
                "Employee",
                {"user_id": user_id, "status": "Active"}
            )
            if employee_exists:
                return user_id
                
    # 2. Fallback to the first enabled user
    for u in users:
        user_id = u.parent
        if frappe.db.get_value("User", user_id, "enabled"):
            return user_id
            
    return None


def generate_approval_flow(doc, designation):
    """
    Generates the approval sequence based on the employee's designation,
    populates the child table 'approval_flow', and sets the initial current approver.

    Flow Logic (canonical per Razeel 2026-06-02 spec):
    - General Manager       : HR  (1 step)
    - HR Coord./Coord./Asst.: GM  (1 step)
    - Area Sales Manager / Accounts Manager (HODs themselves): HR -> GM
    - Sales Executive       : Sales HOD -> HR -> GM
    - Accountant / Purchaser: Accounts Manager (HOD) -> HR -> GM
    - Everyone else         : HR -> GM

    "Sales HOD Leave Approver" covers BOTH Marketing HOD
    (marketing@chundakadan.in) and Northern HOD
    (chundakadannorthasm@gmail.com). Either can approve via the
    widened _caller_can_act_on policy.
    """
    role_sequence = []

    # Sales chain: Sales Executive -> Sales HOD -> HR -> GM
    if designation == "Sales Executive":
        role_sequence = ["Sales HOD Leave Approver", "HR Leave Approver", "GM Leave Approver"]
    # Accounts/Purchasing chain: must clear Accounts Manager (HOD) first
    elif designation in ("Accountant", "Purchase Coordinator", "Purchaser"):
        role_sequence = [
            "Accounts Manager Leave Approver",
            "HR Leave Approver",
            "GM Leave Approver",
        ]
    # HODs / department heads: skip their own level — HR -> GM
    # Includes the historical "Area Sales Manager" / "Accounts Manager"
    # titles AND the current ones used by Arjun (CDN/026/37) and Razeel
    # (CDN/025/020). Matched explicitly so future default-chain changes
    # don't silently affect HOD routing.
    elif designation in (
        "Area Sales Manager",
        "Accounts Manager",
        "Sales& Marketing Manager",          # Arjun (Marketing HOD)
        "Sales & Marketing Manager",         # tolerant of corrected typo
        "Deputy Sales & Marketing Manager",  # Razeel (Northern HOD)
    ):
        role_sequence = ["HR Leave Approver", "GM Leave Approver"]
    # HR staff: HR self-approves, only GM needed
    elif designation in ("HR Coordinator", "Coordinator", "HR Associate"):
        role_sequence = ["GM Leave Approver"]
    # GM: only HR needs to sign off
    elif designation == "General Manager":
        role_sequence = ["HR Leave Approver"]
    # Everyone else (floor staff, BDE, coordinators, etc.): HR -> GM
    else:
        role_sequence = ["HR Leave Approver", "GM Leave Approver"]
        
    # Clear the existing approval flow child table
    doc.set("approval_flow", [])
    
    # Populate the approval flow child table
    for role in role_sequence:
        approver = get_approver_by_role(role)
        if not approver:
            frappe.throw(
                _("Could not locate an active user with the role '{0}'. Please make sure a user is configured with this role and linked to an active Employee.").format(role)
            )
            
        doc.append("approval_flow", {
            "approver": approver,
            "approver_role": role,
            "status": "Pending"
        })
        
    # Set the initial state
    if doc.approval_flow:
        doc.current_approval_index = 0
        doc.current_approver = doc.approval_flow[0].approver
        doc.custom_approval_status = "Pending"
    else:
        doc.current_approval_index = 0
        doc.current_approver = None
        doc.custom_approval_status = "Pending"


def convert_conflicting_attendance_to_on_leave(doc, method=None):
    """Before HRMS validates the Leave Application, find any Attendance
    row that would block the save (status in {Present, Work From Home}
    on a date inside the leave range) and flip it to "On Leave".

    Wired as `before_validate` so this runs BEFORE
    hrms.../leave_application.validate_attendance — that validator only
    raises AttendanceAlreadyMarkedError when it finds rows with status
    "Present" or "Work From Home". By converting them to "On Leave"
    first, the validator sees no conflict.

    Why this is preferable to cancelling the Attendance:
      - audit trail intact — the row stays at docstatus=1
      - monthly attendance sheet still counts the day (as "On Leave")
      - leave_application + leave_type are linked back so HR can trace
        WHY the day became "On Leave"

    Uses frappe.db.set_value to bypass the standard "submitted doc
    cannot be modified" gate. Safe here because Attendance has no GL
    impact and the fields we touch (status, leave_application,
    leave_type) are not financially load-bearing.
    """
    if not (doc.employee and doc.from_date and doc.to_date):
        return

    conflicts = frappe.get_all(
        "Attendance",
        filters={
            "employee": doc.employee,
            "attendance_date": ("between", [doc.from_date, doc.to_date]),
            "status": ("in", ["Present", "Work From Home"]),
            "docstatus": 1,
        },
        fields=["name", "attendance_date"],
        order_by="attendance_date",
    )
    if not conflicts:
        return

    for att in conflicts:
        frappe.db.set_value(
            "Attendance",
            att["name"],
            {
                "status": "On Leave",
                "leave_application": doc.name or None,
                "leave_type": doc.leave_type,
            },
            update_modified=True,
        )

    # Surface what we did — HR should know that attendance was changed
    # implicitly so they can investigate biometric vs leave mismatches.
    dates = ", ".join(
        frappe.utils.formatdate(a["attendance_date"]) for a in conflicts
    )
    frappe.msgprint(
        _("Converted {0} existing Attendance row(s) to 'On Leave' for: {1}").format(
            len(conflicts), dates
        ),
        indicator="orange",
        alert=True,
    )


def validate_leave(doc, method=None):
    """
    Hook triggered on validation of Leave Application.
    - Generates the multi-step approval chain dynamically per designation.
    - Enforces supporting-certificate upload when the selected Leave Type
      has custom_require_certificate flagged (e.g. Sick Leave).
    """
    # Enforce the certificate even on submit attempts (docstatus changes)
    _enforce_certificate_requirement(doc)

    # Do not execute the approval flow logic if document is already
    # submitted or cancelled — the chain was set at draft time.
    if doc.docstatus > 0:
        return

    if not doc.employee:
        return

    designation = frappe.db.get_value("Employee", doc.employee, "designation")

    # Auto generate approval flow on creation or when employee changes
    if doc.is_new():
        generate_approval_flow(doc, designation)
    else:
        db_employee = frappe.db.get_value("Leave Application", doc.name, "employee")
        if db_employee != doc.employee or not doc.approval_flow:
            generate_approval_flow(doc, designation)


def _enforce_certificate_requirement(doc):
    """Block save when the selected Leave Type has
    `custom_require_certificate` ON and no `custom_medical_certificate`
    file is attached. Applies to drafts AND submit attempts.
    """
    if not doc.leave_type:
        return
    require = frappe.db.get_value(
        "Leave Type", doc.leave_type, "custom_require_certificate"
    )
    if not require:
        return
    if not (doc.get("custom_medical_certificate") or "").strip():
        frappe.throw(
            _(
                "{0} requires a supporting certificate. "
                "Please attach a medical certificate or proof document before submitting."
            ).format(doc.leave_type),
            title=_("Certificate Required"),
        )


@frappe.whitelist()
def approve_leave(docname):
    """
    Whitelisted API method to approve the current level of leave application.
    Marks the current approver row as Approved, updates the approved_on timestamp,
    and forwards to the next approver or finalizes the document submission.
    """
    # Load the document
    doc = frappe.get_doc("Leave Application", docname)
    current_user = frappe.session.user

    # Security Validation — see _caller_can_act_on docstring for policy.
    if not _caller_can_act_on(doc):
        frappe.throw(
            _("You are not authorized to approve this leave application. Current approver is: {0}").format(doc.current_approver)
        )

    if doc.custom_approval_status in ["Approved", "Rejected"]:
        frappe.throw(
            _("This leave application has already been processed (Status: {0}).").format(doc.custom_approval_status)
        )

    idx = doc.current_approval_index
    if not doc.approval_flow or idx >= len(doc.approval_flow):
        frappe.throw(_("The approval flow is empty or current index is out of bounds."))

    # Mark the current row approved. Record the actual acting user — the
    # row.approver may have been resolved to a different person at chain
    # creation time, but the audit trail should reflect who really clicked.
    row = doc.approval_flow[idx]
    row.status = "Approved"
    row.approved_on = frappe.utils.now_datetime()
    if current_user != row.approver:
        row.approver = current_user
    
    # Advance to the next level
    next_idx = idx + 1
    doc.flags.ignore_permissions = True

    # HRMS's validate_leave_access (called inside validate_balance_leaves
    # on save/submit) checks both:
    #   1. `frappe.session.user IN (employee_user, leave_approver)` —
    #      reads Employee.leave_approver (NOT the Leave App field).
    #   2. `frappe.has_permission("Employee", "read", employee)` — any
    #      HOD lacks this unless they hold HR User/Manager role.
    # Frappe's has_permission does NOT respect frappe.flags.ignore_
    # permissions in v15, so the only reliable bypass is to temporarily
    # switch session.user to Administrator for the save/submit block.
    # Safe because _caller_can_act_on has ALREADY authorised the
    # original caller. We stamp row.approver = current_user above, so
    # the audit trail is preserved.
    #
    # DRAFT-only: rotate doc.leave_approver to acting user so the
    # standard ERPNext field stays in sync. SKIPPED on submitted (legacy)
    # docs because leave_approver doesn't have allow_on_submit=1 — would
    # throw "Cannot Update After Submit". The Administrator switch below
    # is what actually bypasses the HRMS validator; this rotation is just
    # cosmetic.
    if doc.docstatus == 0:
        doc.leave_approver = current_user

    original_user = frappe.session.user
    saved_flag = frappe.flags.ignore_permissions
    try:
        frappe.set_user("Administrator")
        frappe.flags.ignore_permissions = True
        if next_idx < len(doc.approval_flow):
            # Intermediate step: just route, do NOT submit. The doc stays
            # at docstatus=0 (Draft) so leave balance isn't consumed until
            # the final approver acts.
            doc.current_approval_index = next_idx
            doc.current_approver = doc.approval_flow[next_idx].approver
            doc.custom_approval_status = "Partially Approved"
            if doc.docstatus == 0:
                doc.save()
            else:
                # Backward compatibility: 44 historical leaves are already
                # submitted (created before this draft-while-pending flow).
                # Save in place — the allow_on_submit flag on chain fields
                # makes this legal.
                doc.save()
            frappe.msgprint(
                _("Leave Application partially approved and routed to {0}.").format(doc.current_approver),
                indicator="blue",
            )
        else:
            # Final approval: lock the doc by submitting. Standard ERPNext
            # validators (leave balance, overlap, etc.) fire here.
            doc.custom_approval_status = "Approved"
            doc.current_approver = None
            doc.status = "Approved"
            if doc.docstatus == 0:
                doc.submit()
                msg = _("Leave Application fully approved and submitted!")
            else:
                # Doc was already submitted in a previous flow version — just
                # save the final status updates. allow_on_submit makes this OK.
                doc.flags.ignore_validate = True
                doc.save()
                msg = _("Leave Application fully approved!")
            frappe.msgprint(msg, indicator="green")
    finally:
        frappe.set_user(original_user)
        frappe.flags.ignore_permissions = saved_flag

    return {"success": True}


@frappe.whitelist()
def reject_leave(docname, remarks=None):
    """
    Whitelisted API method to reject the leave application.
    Marks the current level as Rejected, updates status, and stops the flow.
    """
    doc = frappe.get_doc("Leave Application", docname)
    current_user = frappe.session.user

    # Security Validation — see _caller_can_act_on docstring for policy.
    if not _caller_can_act_on(doc):
        frappe.throw(
            _("You are not authorized to reject this leave application. Current approver is: {0}").format(doc.current_approver)
        )

    if doc.custom_approval_status in ["Approved", "Rejected"]:
        frappe.throw(
            _("This leave application has already been processed (Status: {0}).").format(doc.custom_approval_status)
        )

    idx = doc.current_approval_index
    if not doc.approval_flow or idx >= len(doc.approval_flow):
        frappe.throw(_("The approval flow is empty or current index is out of bounds."))

    # Mark the current row rejected and stamp the real acting user.
    row = doc.approval_flow[idx]
    row.status = "Rejected"
    row.approved_on = frappe.utils.now_datetime()
    if current_user != row.approver:
        row.approver = current_user
    if remarks:
        row.remarks = remarks

    # HRMS validate_leave_access tolerance — see approve_leave for why.
    # DRAFT-only rotation: leave_approver isn't allow_on_submit=1, so
    # writing it on a legacy submitted doc throws "Cannot Update After
    # Submit". Administrator switch below is what actually bypasses the
    # validator; this is just cosmetic alignment of the standard field.
    if doc.docstatus == 0:
        doc.leave_approver = current_user
    doc.flags.ignore_permissions = True

    # Finalize rejection. Rejected leaves do NOT consume leave balance,
    # so we don't submit — the doc stays at Draft with status=Rejected
    # (or stays at docstatus=1 if it was a legacy already-submitted doc).
    doc.custom_approval_status = "Rejected"
    doc.status = "Rejected"
    doc.current_approver = None

    # Temporarily run as Administrator so HRMS's validate_leave_access
    # passes (it does an independent Employee read perm check that
    # frappe.flags.ignore_permissions doesn't bypass in v15). Our
    # _caller_can_act_on has already authorised the original caller.
    original_user = frappe.session.user
    saved_flag = frappe.flags.ignore_permissions
    try:
        frappe.set_user("Administrator")
        frappe.flags.ignore_permissions = True
        doc.save()
    finally:
        frappe.set_user(original_user)
        frappe.flags.ignore_permissions = saved_flag
    
    frappe.msgprint(
        _("Leave Application has been rejected."),
        indicator="red"
    )
    
    return {"success": True}


def get_permission_query_conditions(user=None):
    """List-view filter for Leave Application.

    A user can list a leave if ANY of:
      1. they are owner/applicant
      2. they are the resolved current_approver
      3. they are doc.leave_approver (standard ERPNext field)
      4. they hold the role of ANY step in approval_flow (past, present, or
         future) — lets a HOD see leaves heading their way before their
         step becomes current

    Admin / System Manager / HR Manager bypass the filter entirely.
    """
    if not user:
        user = frappe.session.user

    roles = frappe.get_roles(user)
    if user == "Administrator" or "System Manager" in roles or "HR Manager" in roles:
        return ""

    # Build the EXISTS clause that matches "any approval_flow row whose
    # approver_role is in this user's roles". Empty roles list would yield
    # an invalid SQL IN () — sentinel keeps the SQL valid but never matches.
    role_list = roles or ["__noroles__"]
    role_in_sql = ", ".join(frappe.db.escape(r) for r in role_list)
    user_q = frappe.db.escape(user)

    return (
        f"(`tabLeave Application`.owner = {user_q} "
        f"OR `tabLeave Application`.current_approver = {user_q} "
        f"OR `tabLeave Application`.leave_approver = {user_q} "
        f"OR EXISTS ("
        f"  SELECT 1 FROM `tabLeave Approval Detail` flow "
        f"  WHERE flow.parent = `tabLeave Application`.name "
        f"    AND flow.parenttype = 'Leave Application' "
        f"    AND flow.approver_role IN ({role_in_sql})"
        f"))"
    )


def has_permission(doc, ptype="read", user=None):
    """Document-level permission. Mirrors get_permission_query_conditions
    so list view + form view agree on who can see a leave.
    """
    if not user:
        user = frappe.session.user

    roles = frappe.get_roles(user)
    if user == "Administrator" or "System Manager" in roles or "HR Manager" in roles:
        return True

    if doc.owner == user:
        return True
    if doc.current_approver and doc.current_approver == user:
        return True
    if doc.get("leave_approver") and doc.leave_approver == user:
        return True

    # Holds the role of ANY step (past, current, or future)
    for row in getattr(doc, "approval_flow", []) or []:
        if row.approver == user:
            return True
        if row.approver_role and row.approver_role in roles:
            return True

    return False


# ---------------------------------------------------------------------------
# Annual leave auto-allocation
# Driven by Chundakadan Settings.annual_leave_policy + annual_allocation_run_date.
# Two entry points:
#   - maybe_auto_allocate(): cron-triggered daily; runs only on the configured day
#   - allocate_annual_leaves_for_employee(employee): HR Action button on Employee
# ---------------------------------------------------------------------------

import datetime


def _today():
    return frappe.utils.getdate(frappe.utils.nowdate())


def _allocation_window(run_date):
    """Return (from_date, to_date) for the allocation period: the run date
    of THIS year through the day before next year's run date."""
    today = _today()
    if isinstance(run_date, str):
        run_date = frappe.utils.getdate(run_date)
    start = datetime.date(today.year, run_date.month, run_date.day)
    # If today is before this year's run-date, the window already started
    # last year. Shouldn't happen on the cron path, but keep it safe.
    if today < start:
        start = datetime.date(today.year - 1, run_date.month, run_date.day)
    end = datetime.date(start.year + 1, start.month, start.day) - datetime.timedelta(days=1)
    return start, end


def _create_allocation(employee, leave_type, days, from_date, to_date):
    """Create one Leave Allocation. Returns the new doc's name or None
    when skipped (already allocated for the window). carry_forward is
    taken from the Leave Type's own is_carry_forward flag — that's the
    standard ERPNext source of truth, mirroring how Leave Policy
    Assignment behaves."""
    existing = frappe.db.exists(
        "Leave Allocation",
        {
            "employee": employee,
            "leave_type": leave_type,
            "from_date": ["<=", to_date],
            "to_date": [">=", from_date],
            "docstatus": ["!=", 2],
        },
    )
    if existing:
        return None

    carry = frappe.db.get_value("Leave Type", leave_type, "is_carry_forward") or 0

    alloc = frappe.new_doc("Leave Allocation")
    alloc.employee = employee
    alloc.leave_type = leave_type
    alloc.from_date = from_date
    alloc.to_date = to_date
    alloc.new_leaves_allocated = days
    alloc.carry_forward = 1 if carry else 0
    alloc.description = "Auto-allocated via Chundakadan Settings annual policy."
    alloc.insert(ignore_permissions=True)
    alloc.submit()
    return alloc.name


def _get_policy_rows():
    """Return [(leave_type, annual_allocation), ...] from the standard
    Leave Policy linked on Chundakadan Settings. Empty list when no
    policy is linked or it has no rows."""
    settings = frappe.get_cached_doc("Chundakadan Settings")
    lp_name = settings.get("annual_leave_policy")
    if not lp_name:
        return []
    if not frappe.db.exists("Leave Policy", lp_name):
        frappe.throw(_("Chundakadan Settings → Annual Leave Policy points to {0} which doesn't exist.").format(lp_name))
    lp = frappe.get_cached_doc("Leave Policy", lp_name)
    return [(d.leave_type, d.annual_allocation) for d in (lp.leave_policy_details or [])]


@frappe.whitelist()
def allocate_annual_leaves_for_employee(employee):
    """Allocate annual leaves for ONE employee per the Leave Policy
    linked on Chundakadan Settings. Idempotent — re-running on the
    same employee in the same window skips rows already covered."""
    if not employee:
        frappe.throw(_("Employee is required"))

    rows = _get_policy_rows()
    if not rows:
        frappe.throw(_("Chundakadan Settings → Annual Leave Policy is empty or unset."))

    settings = frappe.get_cached_doc("Chundakadan Settings")
    run_date = settings.get("annual_allocation_run_date")
    if not run_date:
        today = _today()
        run_date = datetime.date(today.year, today.month, today.day)

    from_date, to_date = _allocation_window(run_date)

    created, skipped = [], []
    for leave_type, days in rows:
        name = _create_allocation(employee, leave_type, days, from_date, to_date)
        if name:
            created.append({"leave_type": leave_type, "allocation": name})
        else:
            skipped.append({"leave_type": leave_type, "reason": "already_allocated"})

    return {
        "employee": employee,
        "leave_policy": settings.annual_leave_policy,
        "from_date": str(from_date),
        "to_date": str(to_date),
        "created": created,
        "skipped": skipped,
    }


def auto_allocate_annual_leaves():
    """Allocate annual leaves for every Active Employee. Called by the
    daily cron via maybe_auto_allocate (which gates on today's date)."""
    settings = frappe.get_cached_doc("Chundakadan Settings")
    if not settings.get("auto_allocate_annual_leaves"):
        return {"status": "disabled"}
    if not _get_policy_rows():
        return {"status": "no_policy"}

    employees = frappe.get_all("Employee", filters={"status": "Active"}, pluck="name")
    summary = {"total_employees": len(employees), "created": 0, "skipped": 0, "errors": 0}
    for emp in employees:
        try:
            r = allocate_annual_leaves_for_employee(emp)
            summary["created"] += len(r["created"])
            summary["skipped"] += len(r["skipped"])
        except Exception:
            summary["errors"] += 1
            frappe.log_error(
                frappe.get_traceback(),
                f"chundakadan.auto_allocate_annual_leaves[{emp}]",
            )
    frappe.db.commit()
    return summary


def maybe_auto_allocate():
    """Daily cron entry-point. Fires the bulk allocation only when today's
    month + day matches Chundakadan Settings.annual_allocation_run_date.
    Year part of the configured date is ignored — this runs once per year
    on the configured month+day."""
    settings = frappe.get_cached_doc("Chundakadan Settings")
    if not settings.get("auto_allocate_annual_leaves"):
        return
    run_date = settings.get("annual_allocation_run_date")
    if not run_date:
        return
    if isinstance(run_date, str):
        run_date = frappe.utils.getdate(run_date)
    today = _today()
    if today.month == run_date.month and today.day == run_date.day:
        auto_allocate_annual_leaves()
