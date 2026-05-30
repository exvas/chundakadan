# Copyright (c) 2026, Ashkar and contributors
# For license information, please see license.txt

import frappe
from frappe import _

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
    
    Flow Logic:
    - Sales Executive: ASM -> HR -> GM
    - Area Sales Manager: HR -> GM
    - HR Coordinator / Coordinator: GM
    - General Manager: HR
    - Fallback: HR -> GM
    """
    role_sequence = []

    # Sales chain: Sales Executive -> HOD (ASM) -> HR -> GM
    if designation == "Sales Executive":
        role_sequence = ["ASM Leave Approver", "HR Leave Approver", "GM Leave Approver"]
    # Accounts/Purchasing chain: must clear Accounts Manager (HOD) first
    elif designation in ("Accountant", "Purchase Coordinator", "Purchaser"):
        role_sequence = [
            "Accounts Manager Leave Approver",
            "HR Leave Approver",
            "GM Leave Approver",
        ]
    # HODs / department heads: skip their own level
    elif designation in ("Area Sales Manager", "Accounts Manager"):
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
    
    # Security Validation: Only the designated current approver or Administrator can approve
    if current_user != doc.current_approver and current_user != "Administrator":
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
        
    # Mark the current row approved
    row = doc.approval_flow[idx]
    row.status = "Approved"
    row.approved_on = frappe.utils.now_datetime()
    
    # Advance to the next level
    next_idx = idx + 1
    doc.flags.ignore_permissions = True

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

    return {"success": True}


@frappe.whitelist()
def reject_leave(docname, remarks=None):
    """
    Whitelisted API method to reject the leave application.
    Marks the current level as Rejected, updates status, and stops the flow.
    """
    doc = frappe.get_doc("Leave Application", docname)
    current_user = frappe.session.user
    
    # Security Validation: Only the designated current approver or Administrator can reject
    if current_user != doc.current_approver and current_user != "Administrator":
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
        
    # Mark the current row rejected
    row = doc.approval_flow[idx]
    row.status = "Rejected"
    row.approved_on = frappe.utils.now_datetime()
    if remarks:
        row.remarks = remarks
        
    # Finalize rejection. Rejected leaves do NOT consume leave balance,
    # so we don't submit — the doc stays at Draft with status=Rejected
    # (or stays at docstatus=1 if it was a legacy already-submitted doc).
    doc.custom_approval_status = "Rejected"
    doc.status = "Rejected"
    doc.current_approver = None

    doc.flags.ignore_permissions = True
    doc.save()
    
    frappe.msgprint(
        _("Leave Application has been rejected."),
        indicator="red"
    )
    
    return {"success": True}


def get_permission_query_conditions(user=None):
    """
    Custom permission query conditions for Leave Application.
    Ensures employees see their own applications, while current approvers can see their pending ones.
    """
    if not user:
        user = frappe.session.user
        
    if user == "Administrator" or "System Manager" in frappe.get_roles(user) or "HR Manager" in frappe.get_roles(user):
        return ""
        
    return f"(`tabLeave Application`.owner = {frappe.db.escape(user)} OR `tabLeave Application`.current_approver = {frappe.db.escape(user)})"


def has_permission(doc, ptype="read", user=None):
    """
    Custom document-level permission verification.
    Grants access if the user is the owner, a current/past approver, or holds elevated manager roles.
    """
    if not user:
        user = frappe.session.user
        
    if user == "Administrator" or "System Manager" in frappe.get_roles(user) or "HR Manager" in frappe.get_roles(user):
        return True
        
    if doc.owner == user or doc.current_approver == user:
        return True
        
    # Past approvers from the table can read
    for row in getattr(doc, "approval_flow", []):
        if row.approver == user:
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
