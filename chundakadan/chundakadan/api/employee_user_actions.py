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


def _is_hr_dept(department):
    """True if this department needs to see all employees (HR / GM)."""
    if not department:
        return False
    d = department.lower()
    return ("hr" in d) or ("general manager" in d)


def _should_restrict_to_self(emp):
    """Decide whether this user should be restricted to their own
    Employee record via User Permission.

    Restrict (return True) for normal staff — they should only see
    themselves in Employee lists, leave histories, attendance, etc.

    DON'T restrict (return False) for HR / GM / Manager / HOD roles —
    they need to see other employees to approve leaves, run reports,
    manage the org. Auto-detected dynamically from department +
    designation so the rule scales as the org grows.
    """
    if _is_hr_dept(emp.department):
        return False
    if _is_manager_designation(emp.designation):
        return False
    return True


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


def _ensure_mop_mapping(sp_name, company, log):
    """Add Cash + Cheque rows to Chundakadan Settings.mop_mapping for this
    Sales Person, if missing. Idempotent."""
    if not sp_name or not company:
        return
    try:
        cs = frappe.get_single("Chundakadan Settings")
        existing = {(r.sales_person, r.mode_of_payment)
                    for r in (cs.mop_mapping or [])}
        cash_acct = frappe.db.get_value("Account",
            {"company": company, "account_name": "Cash", "is_group": 0}, "name")
        bank_acct = frappe.db.get_value("Account",
            {"company": company, "account_name": ["like", "%Federal-Bank%"],
             "is_group": 0}, "name")
        added = 0
        if (sp_name, "Cash") not in existing and cash_acct:
            cs.append("mop_mapping", {
                "sales_person": sp_name, "company": company,
                "mode_of_payment": "Cash", "account": cash_acct})
            added += 1
        if (sp_name, "Cheque") not in existing and bank_acct:
            cs.append("mop_mapping", {
                "sales_person": sp_name, "company": company,
                "mode_of_payment": "Cheque", "account": bank_acct})
            added += 1
        if added:
            cs.save(ignore_permissions=True)
            log.append(f"Added {added} MOP Mapping row(s) for {sp_name}")
        else:
            log.append(f"MOP Mapping already present for {sp_name}")
    except Exception as e:
        log.append(f"MOP Mapping update failed: {str(e)[:120]}")


def _setup_sales_person_full(employee, log):
    """Lightweight Sales Person setup — ONLY creates/enables the SP record
    + adds MOP rows. Does NOT touch Role Profile, SSA, leave_approver,
    or shift_location (those are Employee Transfer concerns, not "make
    the visit log work" concerns).

    Use this from:
      • create_user_for_employee (during HR Actions Create User)
      • apply_sales_person_setup (the standalone HR Action button)
      • The auto-fix path for the Setup Pending banner
    """
    emp = frappe.get_doc("Employee", employee)
    sp = _ensure_sales_person(emp.name, emp.employee_name, log)
    if sp:
        _ensure_mop_mapping(sp, emp.company, log)
    return sp


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


def _ensure_user_permission(user_id, doctype, name, log,
                              apply_to_all=1, hide_descendants=1, is_default=1):
    """Create User Permission row if not already present.

    Default flags match what HR clicks in the UI:
      • apply_to_all_doctypes=1 — permission applies to every linked DocType
      • hide_descendants=1     — for tree doctypes (Employee/Territory),
                                 children of For Value are also hidden
      • is_default=1           — this value becomes the user's default
                                 in fields linked to that doctype
    """
    if frappe.db.exists("User Permission", {
        "user": user_id, "allow": doctype, "for_value": name,
    }):
        return False
    frappe.get_doc({
        "doctype": "User Permission",
        "user": user_id,
        "allow": doctype,
        "for_value": name,
        "apply_to_all_doctypes": int(apply_to_all),
        "hide_descendants": int(hide_descendants),
        "is_default": int(is_default),
    }).insert(ignore_permissions=True)
    log.append(
        f"User Permission: restrict {doctype}={name}  "
        f"(apply_all={apply_to_all}, hide_desc={hide_descendants}, default={is_default})"
    )
    return True


def _apply_user_permissions(user_id, emp, log):
    """Apply the standard chundakadan User Permission set for this
    employee:

      1. If normal staff (not manager / HR / GM) → restrict Employee=self
         so they only see their own record in Employee lists, leave
         history, attendance dashboard, etc.

      2. ALWAYS restrict by Company (no hard-coded list — picks up the
         employee's actual company from the doc). Only applied when the
         bench has more than one Company configured — otherwise it's
         redundant noise.

    Skipped for HR / GM / Manager / HOD so they can see other employees
    to approve leaves, run reports, manage the org. Decision is
    re-derived from Employee.department + Employee.designation, so
    promoting someone to Manager later just means re-running this action
    (or deleting the existing user permission rows manually).
    """
    # 1. Employee restriction (conditional)
    if _should_restrict_to_self(emp):
        _ensure_user_permission(
            user_id, "Employee", emp.name, log,
            apply_to_all=1, hide_descendants=1, is_default=1,
        )
    else:
        # Manager / HR / GM — they shouldn't be restricted. If a stale
        # Employee=self perm exists from a previous role, REMOVE it so
        # they can see other employees again. (Common scenario: regular
        # staffer gets promoted to Manager; the old restriction would
        # silently keep blocking their new responsibilities.)
        reason = "HR/GM dept" if _is_hr_dept(emp.department) else "manager designation"
        stale = frappe.db.get_value("User Permission", {
            "user": user_id, "allow": "Employee", "for_value": emp.name,
        }, "name")
        if stale:
            frappe.delete_doc("User Permission", stale,
                                force=True, ignore_permissions=True)
            log.append(f"Removed stale Employee=self user permission "
                        f"({reason} — should see other employees)")
        else:
            log.append(f"Skipped Employee user permission ({reason}) — "
                        f"this user needs to see other employees")

    # 2. Company restriction (only meaningful in multi-company benches)
    n_companies = frappe.db.count("Company")
    if emp.company and n_companies > 1:
        _ensure_user_permission(
            user_id, "Company", emp.company, log,
            apply_to_all=1, hide_descendants=0, is_default=1,
        )
    elif emp.company and n_companies <= 1:
        log.append(f"Single-company bench — skipping Company user permission "
                    f"(no other companies to filter out)")


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

    # User Permissions — auto-decides based on department + designation:
    #   • Normal staff: restrict Employee=self + Company=their company
    #   • HR / GM / Manager: skip Employee restriction (need to see all),
    #     still apply Company restriction in multi-company benches
    _apply_user_permissions(new_user.name, emp, log)

    # Sales Person automation — create + add MOP rows so the field_sales
    # mobile app's log_customer_visit etc. work immediately. Lightweight
    # (no SSA / role profile / leave_approver mutations).
    if _is_sales_dept(emp.department):
        _setup_sales_person_full(emp.name, log)

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
def apply_geofence_for_employee(employee, shift_location=None):
    """Set or clear the geofence on every active Shift Assignment for this
    employee.

      • shift_location = "" / None  → CLEAR (field staff, no geofence)
      • shift_location = "HOD" etc. → SET to that Shift Location

    Reuses the same field (Shift Assignment.shift_location) that HRMS
    + the field_sales mobile app's check-in flow read for distance
    enforcement. After this runs, the affected employee should LOG OUT
    + LOG BACK IN on the mobile app so their cached config refreshes —
    the server change alone doesn't reset the client's locally-stored
    geofence state.
    """
    _check_hr_user()
    emp = frappe.get_doc("Employee", employee)
    target = (shift_location or "").strip() or None
    if target and not frappe.db.exists("Shift Location", target):
        frappe.throw(_("Shift Location '{0}' does not exist.").format(target))

    log = []
    active = frappe.get_all("Shift Assignment",
        filters={"employee": emp.name, "docstatus": 1, "status": "Active"},
        fields=["name", "shift_location"])
    if not active:
        log.append("No active Shift Assignment found — create one first via "
                    "HR Actions → Assign Shift before setting geofence.")
    else:
        changed = 0
        for sa in active:
            current = sa.shift_location or None
            if current == target:
                continue
            frappe.db.set_value("Shift Assignment", sa.name, "shift_location",
                                 target, update_modified=False)
            label = target or "<cleared — field staff>"
            log.append(f"Shift Assignment {sa.name}: {current or '<none>'} → {label}")
            changed += 1
        if not changed:
            log.append(f"All active Shift Assignments already at "
                        f"{target or '<cleared>'} — no change")

    log.append("⚠ Remind the employee to log out + log back in on the mobile "
                "app so their cached geofence config refreshes.")

    emp.add_comment("Info",
        "<b>Geofence updated via HR Action</b><br>"
        + "<br>".join("• " + ln for ln in log)
        + f"<br><br><i>By {frappe.session.user}</i>")
    frappe.db.commit()
    return {"shift_location": target, "log": log}


@frappe.whitelist()
def send_mobile_relogin_reminder(employee, reason=""):
    """Notify an employee to log out + log back in on their mobile app.

    Why this exists: classic case (Jazeel 2026-06-22) — HR changes
    Employee.shift_location server-side to clear the geofence, but the
    field_sales mobile app cached the OLD office-staff config at login
    and keeps enforcing the 300m radius locally. The mobile only re-reads
    the config on fresh login. So after any server-side change to a
    field the mobile caches (shift_location / role / department), HR
    needs to ping the employee to refresh their app.

    Mechanism: writes a Notification Log entry the employee sees in
    their mobile app's bell icon (chundakadan/public/js wires this).
    """
    _check_hr_user()
    user_id = frappe.db.get_value("Employee", employee, "user_id")
    if not user_id:
        frappe.throw(_("Employee has no linked User — nothing to notify"))
    emp_name = frappe.db.get_value("Employee", employee, "employee_name")
    subject = "Please log out and log back in on the mobile app"
    body = (reason or
            "HR has updated your settings on the server. Please log out + "
            "log back in on the chundakadan mobile app so your cached "
            "configuration refreshes. Without this, you may see stale "
            "geofence / permission errors.")
    try:
        nl = frappe.get_doc({
            "doctype": "Notification Log",
            "subject": subject,
            "email_content": body,
            "for_user": user_id,
            "type": "Alert",
            "document_type": "Employee",
            "document_name": employee,
        })
        nl.flags.ignore_permissions = True
        nl.insert()
    except Exception as e:
        frappe.throw(_("Could not create Notification Log: {0}").format(str(e)[:120]))

    frappe.get_doc("Employee", employee).add_comment("Info",
        f"<b>Mobile re-login reminder sent</b><br>"
        f"To: {user_id}<br>"
        f"Reason: {frappe.utils.escape_html(reason or '(default)')}"
        f"<br><br><i>By {frappe.session.user}</i>")
    frappe.db.commit()
    return {"sent_to": user_id, "notification": nl.name}


@frappe.whitelist()
def dashboard_update(employee, action, value=None):
    """Generic inline-update entry point used by the Setup Dashboard
    dialog. Each `action` maps to a specific change so HR can edit
    values without leaving the dashboard. Permission gate is the same
    HR Manager/HR User check as everywhere else.

    Supported actions:
      • reports_to          → set Employee.reports_to (or clear if value="")
      • shift_type          → cancel active SA, create new SA with chosen shift_type
      • sales_person_toggle → enable/disable Sales Person
      • manager_details_add → add row to Chundakadan Settings.manager_details
      • manager_details_remove → remove row
    """
    _check_hr_user()
    emp = frappe.get_doc("Employee", employee)
    log = []

    if action == "reports_to":
        new = (value or "").strip() or None
        if new and not frappe.db.exists("Employee", new):
            frappe.throw(_("Employee '{0}' not found").format(new))
        if emp.reports_to == new:
            log.append("reports_to already set to that value")
        else:
            old = emp.reports_to or "<none>"
            frappe.db.set_value("Employee", emp.name, "reports_to", new,
                                  update_modified=False)
            log.append(f"reports_to: {old} → {new or '<cleared>'}")

    elif action == "shift_type":
        new = (value or "").strip()
        if not new:
            frappe.throw(_("Pick a shift type"))
        if not frappe.db.exists("Shift Type", new):
            frappe.throw(_("Shift Type '{0}' not found").format(new))
        # Cancel current active SAs, create one new at new shift_type
        active = frappe.get_all("Shift Assignment",
            filters={"employee": emp.name, "docstatus": 1, "status": "Active"},
            fields=["name", "shift_type", "shift_location", "start_date"])
        if active and all(sa.shift_type == new for sa in active):
            log.append("Already on that shift type — no change")
        else:
            kept_location = active[0].shift_location if active else None
            for sa in active:
                try:
                    d = frappe.get_doc("Shift Assignment", sa.name)
                    d.cancel()
                    log.append(f"Cancelled SA {sa.name} ({sa.shift_type})")
                except Exception as e:
                    log.append(f"Could not cancel {sa.name}: {str(e)[:80]}")
            try:
                sa = frappe.get_doc({
                    "doctype": "Shift Assignment",
                    "employee": emp.name,
                    "company": emp.company,
                    "shift_type": new,
                    "shift_location": kept_location,
                    "status": "Active",
                    "start_date": nowdate(),
                })
                sa.flags.ignore_permissions = True
                sa.flags.ignore_mandatory = True
                sa.insert()
                sa.submit()
                log.append(f"Created new SA {sa.name} ({new}) — geofence carried over: {kept_location or '<none>'}")
            except Exception as e:
                log.append(f"Could not create new SA: {str(e)[:120]}")

    elif action == "sales_person_toggle":
        sp = frappe.db.get_value("Sales Person", {"employee": emp.name},
            ["name", "enabled"], as_dict=True)
        if not sp:
            frappe.throw(_("No Sales Person record — use Setup Sales Person first"))
        new_state = 0 if sp.enabled else 1
        frappe.db.set_value("Sales Person", sp.name, "enabled", new_state,
                              update_modified=False)
        log.append(f"Sales Person {sp.name}: enabled {sp.enabled} → {new_state}")

    elif action == "manager_details_add":
        cs = frappe.get_single("Chundakadan Settings")
        if any(r.employee == emp.name for r in (cs.manager_details or [])):
            log.append("Already in manager_details — no change")
        else:
            cs.append("manager_details", {
                "employee": emp.name,
                "allow_edit": 1, "allow_submit": 1, "workflow_approval": 1,
            })
            cs.save(ignore_permissions=True)
            log.append("Added to Chundakadan Settings → manager_details")

    elif action == "manager_details_remove":
        cs = frappe.get_single("Chundakadan Settings")
        before = len(cs.manager_details or [])
        cs.manager_details = [r for r in (cs.manager_details or [])
                                if r.employee != emp.name]
        if before != len(cs.manager_details):
            cs.save(ignore_permissions=True)
            log.append("Removed from Chundakadan Settings → manager_details")
        else:
            log.append("Not in manager_details — no change")

    else:
        frappe.throw(_("Unknown dashboard action: {0}").format(action))

    emp.add_comment("Info",
        f"<b>Dashboard update via HR Action — {action}</b><br>"
        + "<br>".join("• " + ln for ln in log)
        + f"<br><br><i>By {frappe.session.user}</i>")
    frappe.db.commit()
    return {"log": log}


@frappe.whitelist()
def get_employee_dashboard(employee):
    """Single-pane snapshot of everything assigned/linked to this employee
    — used by the 'Setup Dashboard' HR Action button to give HR a
    complete picture in one dialog instead of bouncing between 6+
    doctypes. Each section returns enough data for the UI to render
    a ✓/✗ indicator + an inline action button to fix gaps.

    Sections returned (in display order):
      1. user_account
      2. user_permissions
      3. sales_person
      4. geofence
      5. leave_allocation
      6. shift_assignment
      7. salary_structure
      8. reports_to
      9. manager_details
    """
    _check_hr_user()
    emp = frappe.get_doc("Employee", employee)
    is_sales = _is_sales_dept(emp.department)
    out = {
        "employee": emp.name,
        "employee_name": emp.employee_name,
        "department": emp.department,
        "designation": emp.designation,
        "is_sales_dept": is_sales,
        "sections": {},
    }

    # 1. User Account
    user_row = None
    if emp.user_id:
        user_row = frappe.db.get_value("User", emp.user_id,
            ["enabled", "user_type", "last_login"], as_dict=True) or {}
        roles = frappe.get_roles(emp.user_id)
    else:
        roles = []
    out["sections"]["user_account"] = {
        "ok": bool(user_row and user_row.get("enabled")),
        "user_id": emp.user_id,
        "enabled": bool(user_row and user_row.get("enabled")) if user_row else None,
        "last_login": str(user_row["last_login"]) if user_row and user_row.get("last_login") else "",
        "roles": sorted(set(r for r in roles if r not in ("All", "Guest"))),
    }

    # 2. User Permissions
    needs_emp_perm = _should_restrict_to_self(emp) if emp.user_id else False
    has_emp_perm = bool(emp.user_id and frappe.db.exists("User Permission", {
        "user": emp.user_id, "allow": "Employee", "for_value": emp.name}))
    n_companies = frappe.db.count("Company")
    needs_company_perm = bool(emp.user_id and emp.company and n_companies > 1)
    has_company_perm = bool(emp.user_id and emp.company and frappe.db.exists(
        "User Permission",
        {"user": emp.user_id, "allow": "Company", "for_value": emp.company}))
    out["sections"]["user_permissions"] = {
        "ok": bool(emp.user_id) and (not needs_emp_perm or has_emp_perm)
              and (not needs_company_perm or has_company_perm)
              and not ((not needs_emp_perm) and has_emp_perm),
        "needs_employee_perm": needs_emp_perm,
        "has_employee_perm": has_emp_perm,
        "needs_company_perm": needs_company_perm,
        "has_company_perm": has_company_perm,
        "stale_employee_perm": (not needs_emp_perm) and has_emp_perm,
    }

    # 3. Sales Person
    if is_sales:
        sp = frappe.db.get_value("Sales Person", {"employee": emp.name},
            ["name", "enabled"], as_dict=True)
        mop_rows = 0
        if sp:
            mop_rows = frappe.db.count("Chundakadan Sales Person MOP",
                {"sales_person": sp.name})
        out["sections"]["sales_person"] = {
            "applicable": True,
            "ok": bool(sp and sp.enabled),
            "name": sp.name if sp else None,
            "enabled": bool(sp and sp.enabled) if sp else None,
            "mop_rows": mop_rows,
        }
    else:
        out["sections"]["sales_person"] = {
            "applicable": False, "ok": True,
            "note": "Not applicable (not in Sales/Marketing department)",
        }

    # 4. Geofence (Shift Assignment.shift_location)
    active_sa = frappe.get_all("Shift Assignment",
        filters={"employee": emp.name, "docstatus": 1, "status": "Active"},
        fields=["name", "shift_type", "shift_location", "start_date", "end_date"])
    sl_values = sorted(set(sa.shift_location or "" for sa in active_sa))
    out["sections"]["geofence"] = {
        "applicable": bool(active_sa),
        "expected": "" if is_sales else "HOD",   # field staff: none, office: HOD
        "actual": sl_values[0] if len(sl_values) == 1 else "<mixed>",
        "ok": (
            (is_sales and all(not (sa.shift_location or "") for sa in active_sa))
            or ((not is_sales) and all((sa.shift_location or "") == "HOD" for sa in active_sa))
        ) if active_sa else False,
        "active_assignments": [
            {"name": sa.name, "shift_type": sa.shift_type,
             "shift_location": sa.shift_location or ""}
            for sa in active_sa
        ],
        "available_locations": frappe.db.sql_list(
            "SELECT name FROM `tabShift Location` ORDER BY name"),
    }

    # 5. Leave Allocation (covering today)
    from frappe.utils import nowdate
    n_alloc = frappe.db.count("Leave Allocation", {
        "employee": emp.name, "docstatus": 1,
        "from_date": ["<=", nowdate()], "to_date": [">=", nowdate()],
    })
    out["sections"]["leave_allocation"] = {
        "ok": n_alloc > 0,
        "count": n_alloc,
    }

    # 6. Shift Assignment (presence)
    out["sections"]["shift_assignment"] = {
        "ok": bool(active_sa),
        "count": len(active_sa),
        "shifts": [sa.shift_type for sa in active_sa],
    }

    # 7. Salary Structure Assignment (latest active)
    ssa = frappe.db.get_value("Salary Structure Assignment",
        {"employee": emp.name, "docstatus": 1},
        ["name", "salary_structure", "base", "from_date"], as_dict=True,
        order_by="from_date desc")
    out["sections"]["salary_structure"] = {
        "ok": bool(ssa),
        "name": ssa.name if ssa else None,
        "structure": ssa.salary_structure if ssa else None,
        "base": ssa.base if ssa else None,
        "from_date": str(ssa.from_date) if ssa and ssa.from_date else None,
    }

    # 8. Reports To
    out["sections"]["reports_to"] = {
        "ok": bool(emp.reports_to),
        "reports_to": emp.reports_to,
        "reports_to_name": (frappe.db.get_value("Employee", emp.reports_to,
                                                 "employee_name") if emp.reports_to else None),
    }

    # 9. Manager Details (Chundakadan Settings child)
    md = frappe.db.get_value("Chundakadan Manager Detail",
        {"employee": emp.name, "parent": "Chundakadan Settings"},
        ["allow_edit", "allow_submit", "workflow_approval"], as_dict=True)
    out["sections"]["manager_details"] = {
        "ok": bool(md),
        "in_table": bool(md),
        "allow_edit": bool(md and md.allow_edit) if md else False,
        "allow_submit": bool(md and md.allow_submit) if md else False,
        "workflow_approval": bool(md and md.workflow_approval) if md else False,
        "expected": _is_manager_designation(emp.designation),
    }

    return out


@frappe.whitelist()
def apply_sales_person_setup_for_employee(employee):
    """HR-runnable: setup / repair the Sales Person + MOP for a sales-dept
    employee. Idempotent. Fixes the 'Missing sales_person' error on the
    field_sales mobile visit log without needing IT staff."""
    _check_hr_user()
    emp = frappe.get_doc("Employee", employee)
    if not _is_sales_dept(emp.department):
        frappe.throw(_("This is for Sales/Marketing employees only. "
                       "Current department: {0}").format(emp.department))
    log = []
    sp = _setup_sales_person_full(emp.name, log)
    if not log:
        log.append("All sales person setup already in place — no change")
    emp.add_comment(
        "Info",
        "<b>Sales Person setup applied via HR Action</b><br>"
        + "<br>".join("• " + ln for ln in log)
        + f"<br><br><i>By {frappe.session.user}</i>",
    )
    frappe.db.commit()
    return {"sales_person": sp, "log": log}


@frappe.whitelist()
def apply_user_permissions_for_employee(employee):
    """Apply / fix the standard User Permission set for an EXISTING
    employee + user. Useful when:
      • User was created externally (not via Create User & Setup)
      • Department changed (manager promotion → still has self-restrict)
      • New company added (need Company restriction now)
    Idempotent — won't duplicate existing rows."""
    _check_hr_user()
    emp = frappe.get_doc("Employee", employee)
    if not emp.user_id:
        frappe.throw(_("No User linked to this employee. Click Create User & Setup first."))

    log = []
    _apply_user_permissions(emp.user_id, emp, log)
    if not log:
        log.append("All required user permissions already in place — no change")

    emp.add_comment(
        "Info",
        "<b>User Permissions applied via HR Action</b><br>"
        + "<br>".join("• " + ln for ln in log)
        + f"<br><br><i>By {frappe.session.user}</i>",
    )
    frappe.db.commit()
    return {"user": emp.user_id, "log": log}


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
        # Use the User._reset_password method directly — this generates a
        # reset key, stamps last_reset_password_key_generated_on, and emails
        # the link. Wrap user_doc fetch in ignore_permissions because plain
        # HR User can't read the User doctype without help.
        try:
            user_doc = frappe.get_doc("User", user_id)
            user_doc.validate_reset_password()
            user_doc._reset_password(send_email=True)
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

    # 3. Employee.status = Left + relieving_date.
    # ERPNext blocks Active → Left if anyone reports_to this employee
    # (InactiveEmployeeStatusError). The user disable + session revoke
    # above is the security-critical part — degrade gracefully if the
    # status change fails so HR can fix the reports-to chain separately.
    if emp.status != "Left":
        emp.status = "Left"
        emp.relieving_date = getdate(relieving_date)
        if reason and not emp.reason_for_leaving:
            emp.reason_for_leaving = reason
        emp.flags.ignore_permissions = True
        try:
            emp.save()
            log.append(f"Employee marked Left, relieving_date={relieving_date}")
        except Exception as e:
            # Rollback the in-memory mutation so subsequent reads are clean
            emp.reload()
            err_msg = str(e)
            # Surface the specific blocker (usually reports_to) to HR
            if "reporting to" in err_msg or "Inactive" in err_msg:
                log.append("⚠ Employee status NOT changed — other employees still "
                            "report to this person. Reassign their reports_to "
                            "and then click Disable User again.")
            else:
                log.append(f"⚠ Employee status NOT changed: {err_msg[:150]}")

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
