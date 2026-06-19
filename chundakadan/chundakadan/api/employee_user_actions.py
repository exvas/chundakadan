# Copyright (c) 2026, Ashkar and contributors
# For license information, please see license.txt

"""HR-friendly user-management actions on the Employee form.

Lets HR (no IT knowledge) do four things from the Employee → HR Actions
dropdown without touching the User doctype directly:

  1. create_user_for_employee — Create User + link + role profile +
     sales person + manager_details, all in one click.
  2. reset_employee_password  — Set a new password OR send a reset link.
  3. disable_employee_user    — Exit-employee flow. Disable user,
     revoke sessions, mark Employee=Left, disable sales person, remove
     from manager_details.
  4. enable_employee_user     — Re-hire. Reverse of #3.

Every action is logged as an Info Comment on the Employee doc so HR can
see who did what (audit trail). Re-uses the chain DEPT_TO_STRUCTURE
mapping + sales-person helpers from doc_events/employee_transfer.py so
the side-effects stay consistent with what a normal Employee Transfer
applies.
"""

import frappe
from frappe import _
from frappe.utils import getdate, nowdate, validate_email_address

# Re-use the canonical department → (salary_structure, role_profile) map
# so new-employee onboarding uses the SAME role profile that Employee
# Transfer applies when someone moves into that department.
from chundakadan.doc_events.employee_transfer import DEPT_TO_STRUCTURE


# ---------- Permission guard ---------------------------------------------------


def _check_hr_user():
    """Only HR or Administrator can run these. Throw if not authorised.

    Caller's roles are checked at the request entry point so the more
    intrusive operations (delete user, disable user) can't be triggered
    by random Sales Executives clicking through the API.
    """
    roles = set(frappe.get_roles(frappe.session.user))
    allowed = {"Administrator", "HR Manager", "HR User", "System Manager"}
    if not (roles & allowed):
        frappe.throw(
            _("Only HR Manager / HR User can run this action."),
            frappe.PermissionError,
        )


# ---------- Department / designation classifiers ------------------------------


def _resolve_role_profile_for_dept(department):
    """Return Role Profile name from DEPT_TO_STRUCTURE for the given dept,
    or None if no match. Substring + case-insensitive match (same shape
    as employee_transfer._resolve_dept_targets so onboarding ≡ transfer).
    """
    if not department:
        return None
    # Strip " - <abbr>" suffix that ERPNext appends to department names
    base = department.split(" - ")[0].strip()
    if base in DEPT_TO_STRUCTURE:
        return DEPT_TO_STRUCTURE[base][1]
    lower = base.lower()
    for key, (_struct, role_profile) in DEPT_TO_STRUCTURE.items():
        if key.lower() in lower or lower in key.lower():
            return role_profile
    return None


def _is_sales_dept(department):
    return bool(department and "sales" in department.lower())


def _is_manager_designation(designation):
    """True for GM / HOD / Manager-type designations that should be
    added to Chundakadan Settings.manager_details by default."""
    if not designation:
        return False
    d = designation.lower()
    for kw in ("manager", " hod", "general manager", "gm", "head"):
        if kw.strip() in d:
            return True
    return False


# ---------- Sales person helpers (subset of _apply_to_sales) ------------------


def _ensure_sales_person(employee, employee_name, log):
    """Create or re-enable a Sales Person record for this employee."""
    sp_name = frappe.db.get_value("Sales Person", {"employee": employee}, "name")
    if sp_name:
        if not frappe.db.get_value("Sales Person", sp_name, "enabled"):
            frappe.db.set_value("Sales Person", sp_name, "enabled", 1,
                                 update_modified=False)
            log.append(f"Re-enabled Sales Person: {sp_name}")
        return sp_name
    parent = (frappe.db.get_value("Sales Person",
                {"is_group": 1, "parent_sales_person": ""}, "name")
              or frappe.db.get_value("Sales Person", {"is_group": 1}, "name")
              or "Sales Team")
    try:
        sp = frappe.get_doc({
            "doctype": "Sales Person",
            "sales_person_name": employee_name,
            "employee": employee,
            "enabled": 1,
            "is_group": 0,
            "parent_sales_person": parent,
        })
        sp.insert(ignore_permissions=True)
        log.append(f"Created Sales Person: {sp.name}")
        return sp.name
    except Exception as e:
        log.append(f"Sales Person create failed: {str(e)[:120]}")
        return None


def _disable_sales_person(employee, log):
    sp_name = frappe.db.get_value("Sales Person", {"employee": employee}, "name")
    if not sp_name:
        return
    if frappe.db.get_value("Sales Person", sp_name, "enabled"):
        frappe.db.set_value("Sales Person", sp_name, "enabled", 0,
                             update_modified=False)
        log.append(f"Disabled Sales Person: {sp_name}")


# ---------- Manager details helpers -------------------------------------------


def _add_to_manager_details(employee, allow_edit=1, allow_submit=1,
                              workflow_approval=1, log=None):
    """Add this Employee to Chundakadan Settings.manager_details if missing."""
    log = log if log is not None else []
    cs = frappe.get_single("Chundakadan Settings")
    if any(r.employee == employee for r in (cs.manager_details or [])):
        log.append(f"Already in manager_details: {employee}")
        return
    cs.append("manager_details", {
        "employee": employee,
        "allow_edit": int(allow_edit),
        "allow_submit": int(allow_submit),
        "workflow_approval": int(workflow_approval),
    })
    cs.save(ignore_permissions=True)
    log.append(f"Added to Chundakadan Settings → manager_details")


def _remove_from_manager_details(employee, log):
    cs = frappe.get_single("Chundakadan Settings")
    before = len(cs.manager_details or [])
    cs.manager_details = [r for r in (cs.manager_details or [])
                           if r.employee != employee]
    after = len(cs.manager_details)
    if before != after:
        cs.save(ignore_permissions=True)
        log.append(f"Removed from Chundakadan Settings → manager_details")


# ---------- User Permission helpers -------------------------------------------


def _ensure_user_permission(user_id, doctype, name, log):
    """Create User Permission row if not already present."""
    if frappe.db.exists("User Permission", {
        "user": user_id, "allow": doctype, "for_value": name,
    }):
        return
    frappe.get_doc({
        "doctype": "User Permission",
        "user": user_id,
        "allow": doctype,
        "for_value": name,
        "apply_to_all_doctypes": 1,
    }).insert(ignore_permissions=True)
    log.append(f"User Permission: restrict {doctype} = {name}")


# ---------- Endpoints ----------------------------------------------------------


@frappe.whitelist()
def create_user_for_employee(employee, email=None, send_welcome_email=1,
                              is_manager=None):
    """Create + link a User for this Employee in one click.

    Steps:
      1. Validate employee + check no user_id yet
      2. Validate email (use Employee.company_email if not provided)
      3. Create User with role profile derived from department
      4. Stamp Employee.user_id + create User Permission
      5. If Sales/Marketing dept: create Sales Person
      6. If is_manager (auto-detected from designation if omitted):
         add to Chundakadan Settings → manager_details
      7. Optionally send welcome email with password setup link
    """
    _check_hr_user()
    emp = frappe.get_doc("Employee", employee)
    log = []

    if emp.user_id:
        frappe.throw(_("This employee is already linked to user {0}.")
                      .format(emp.user_id))

    email = (email or emp.company_email or emp.personal_email or "").strip().lower()
    if not email:
        frappe.throw(_("Email is required. Set Employee.company_email or "
                       "pass email in the dialog."))
    validate_email_address(email, throw=True)

    if frappe.db.exists("User", email):
        # Edge case: user exists but isn't linked to anyone — link it
        existing = frappe.get_doc("User", email)
        if frappe.db.exists("Employee", {"user_id": email}):
            frappe.throw(_("Email {0} is already linked to another employee.")
                          .format(email))
        log.append(f"User {email} already existed — linking to this employee")
        new_user = existing
        # Ensure enabled
        if not new_user.enabled:
            new_user.enabled = 1
            new_user.save(ignore_permissions=True)
            log.append("Re-enabled existing User")
    else:
        # Create fresh User
        role_profile = _resolve_role_profile_for_dept(emp.department)
        new_user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": emp.first_name or emp.employee_name.split()[0],
            "last_name": emp.last_name or "",
            "enabled": 1,
            "send_welcome_email": 1 if int(send_welcome_email or 0) else 0,
            "user_type": "System User",
            "role_profile_name": role_profile or "",
        })
        new_user.flags.ignore_permissions = True
        new_user.insert()
        log.append(f"Created User: {email}"
                    + (f" with Role Profile: {role_profile}" if role_profile else " (no role profile mapped)"))

    # Link to employee
    frappe.db.set_value("Employee", employee, "user_id", new_user.name)
    log.append(f"Linked Employee.user_id → {new_user.name}")

    # User Permission so they only see their own Employee record
    _ensure_user_permission(new_user.name, "Employee", employee, log)

    # Sales Person automation
    if _is_sales_dept(emp.department):
        _ensure_sales_person(employee, emp.employee_name, log)

    # Manager details automation
    if is_manager is None:
        is_manager_flag = _is_manager_designation(emp.designation)
    else:
        is_manager_flag = bool(int(is_manager))
    if is_manager_flag:
        _add_to_manager_details(employee, log=log)

    # Audit log
    frappe.get_doc("Employee", employee).add_comment(
        "Info",
        "<b>User created via HR Action</b><br>" + "<br>".join("• " + ln for ln in log)
        + f"<br><br><i>By {frappe.session.user}</i>",
    )
    frappe.db.commit()

    return {
        "user": new_user.name,
        "log": log,
        "welcome_email_sent": bool(int(send_welcome_email or 0)),
    }


@frappe.whitelist()
def reset_employee_password(employee, new_password=None, send_reset_email=0):
    """Reset password for the User linked to this employee.

    If new_password is given, set it directly.
    Otherwise, send a password-reset link to the user's email.
    """
    _check_hr_user()
    user_id = frappe.db.get_value("Employee", employee, "user_id")
    if not user_id:
        frappe.throw(_("No User is linked to this employee."))

    log = []
    if int(send_reset_email or 0) and not new_password:
        from frappe.utils.password import update_password
        from frappe.core.doctype.user.user import reset_password
        try:
            user = frappe.get_doc("User", user_id)
            user.reset_password(send_email=True)
            log.append(f"Password-reset email sent to {user_id}")
        except Exception as e:
            frappe.throw(_("Failed to send reset email: {0}").format(str(e)))
    else:
        if not new_password or len(new_password) < 6:
            frappe.throw(_("New password must be at least 6 characters."))
        from frappe.utils.password import update_password
        update_password(user_id, new_password)
        log.append(f"Password updated for {user_id}")

    frappe.get_doc("Employee", employee).add_comment(
        "Info",
        "<b>Password reset via HR Action</b><br>" + "<br>".join("• " + ln for ln in log)
        + f"<br><br><i>By {frappe.session.user}</i>",
    )
    frappe.db.commit()
    return {"user": user_id, "log": log}


@frappe.whitelist()
def disable_employee_user(employee, relieving_date=None, reason=None):
    """Exit-employee flow: disable User + revoke sessions + mark Employee=Left +
    disable Sales Person + remove from manager_details."""
    _check_hr_user()
    emp = frappe.get_doc("Employee", employee)
    log = []

    relieving_date = relieving_date or nowdate()
    reason = (reason or "").strip()

    # 1. Disable User
    if emp.user_id:
        if frappe.db.get_value("User", emp.user_id, "enabled"):
            frappe.db.set_value("User", emp.user_id, "enabled", 0,
                                 update_modified=False)
            log.append(f"Disabled User: {emp.user_id}")
            # 2. Revoke sessions (force logout)
            try:
                from frappe.sessions import delete_sessions
                deleted = frappe.db.sql(
                    "DELETE FROM `tabSessions` WHERE user=%s", emp.user_id)
                log.append(f"Revoked active sessions for {emp.user_id}")
            except Exception as e:
                log.append(f"Session revoke failed: {str(e)[:80]}")
        else:
            log.append(f"User {emp.user_id} was already disabled")
    else:
        log.append("No User linked — skipping user disable")

    # 3. Employee.status = Left + relieving_date
    if emp.status != "Left":
        emp.status = "Left"
        emp.relieving_date = getdate(relieving_date)
        if reason and not emp.reason_for_leaving:
            emp.reason_for_leaving = reason
        emp.flags.ignore_permissions = True
        emp.save()
        log.append(f"Employee marked Left, relieving_date={relieving_date}")

    # 4. Disable Sales Person
    _disable_sales_person(employee, log)

    # 5. Remove from manager_details
    _remove_from_manager_details(employee, log)

    # Audit
    emp.add_comment(
        "Info",
        f"<b>Employee exit via HR Action</b><br>"
        + "<br>".join("• " + ln for ln in log)
        + (f"<br>• Reason: {reason}" if reason else "")
        + f"<br><br><i>By {frappe.session.user}</i>",
    )
    frappe.db.commit()
    return {"log": log}


@frappe.whitelist()
def enable_employee_user(employee):
    """Re-hire flow: re-enable User + mark Employee=Active + re-enable Sales
    Person if applicable. Does NOT auto-restore manager_details (HR can
    re-add manually if needed — usually the role changed on re-hire)."""
    _check_hr_user()
    emp = frappe.get_doc("Employee", employee)
    log = []

    if not emp.user_id:
        frappe.throw(_("No User is linked to this employee."))
    if frappe.db.get_value("User", emp.user_id, "enabled"):
        log.append(f"User {emp.user_id} was already enabled")
    else:
        frappe.db.set_value("User", emp.user_id, "enabled", 1,
                             update_modified=False)
        log.append(f"Re-enabled User: {emp.user_id}")

    if emp.status == "Left":
        emp.status = "Active"
        emp.relieving_date = None
        emp.flags.ignore_permissions = True
        emp.save()
        log.append("Employee status → Active, relieving_date cleared")

    # Re-enable sales person if dept is Sales
    if _is_sales_dept(emp.department):
        _ensure_sales_person(employee, emp.employee_name, log)

    emp.add_comment(
        "Info",
        "<b>Employee re-activated via HR Action</b><br>"
        + "<br>".join("• " + ln for ln in log)
        + f"<br><br><i>By {frappe.session.user}</i>",
    )
    frappe.db.commit()
    return {"log": log}
