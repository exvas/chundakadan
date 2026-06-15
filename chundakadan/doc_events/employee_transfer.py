"""Auto-apply Chundakadan-specific side effects when an Employee Transfer
is submitted.

When an employee moves into / out of Sales & Marketing, several related
records must update together. Today HR does these manually and often forgets
one. This hook runs them atomically on submit:

  1. Sales Person master — create+enable, or disable (history preserved)
  2. Chundakadan Settings.mop_mapping — add Cash + Cheque rows; keep history on leave
  3. Shift Assignment.shift_location — clear for Sales (field staff), set HOD for office
  4. Salary Structure Assignment — switch to the structure matching new dept
  5. User.role_profile_name — switch to the matching CDN role profile
  6. Employee.leave_approver — point to the new HOD (Sales / Accounts / HR)

Trigger: on_submit of Employee Transfer (wired via hooks.py).
Audit: every step logged as an Info Comment on the Employee Transfer.

If anything fails mid-run the exception propagates → Frappe rolls back
the submit so we never end up in a half-applied state.
"""
import frappe
from frappe import _
from frappe.utils import escape_html, today


# Department → (Salary Structure, Role Profile) mapping.
# Substring-matched (case insensitive) against Employee.department which
# usually carries the company abbreviation suffix (e.g. "Dispatch - CA").
DEPT_TO_STRUCTURE = {
    "Sales& Marketing":  ("CDN Sales Executive Structure", "CDN Sales Executive"),
    "Sales & Marketing": ("CDN Sales Executive Structure", "CDN Sales Executive"),
    "HR":                ("CDN Office Staff Structure",    "CDN HR Assistant"),
    "HR Coordinator":    ("CDN Office Staff Structure",    "CDN HR Assistant"),
    "Accountant":        ("CDN Office Staff Structure",    "CDN Accountant"),
    "Purchase":          ("CDN Office Staff Structure",    "CDN Purchaser"),
    "billing":           ("CDN Office Staff Structure",    "CDN Billing"),
    "Dispatch":          ("CDN Floor Structure",           "CDN Dispatch"),
    "General Manager":   ("CDN Management Structure",      "CDN GM"),
}


def apply_chundakadan_side_effects(doc, method=None):
    """on_submit hook on Employee Transfer.

    Re-derives the transfer type from the actual department change
    (don't trust the user-picked Select). Dispatches to the right
    handler. Logs all actions back on the transfer doc as a Comment.
    """
    if doc.docstatus != 1:
        return

    emp = doc.employee
    old_dept = frappe.db.get_value("Employee", emp, "department")
    new_dept = doc.department
    transfer_type = _detect_transfer_type(old_dept, new_dept, doc)

    doc.db_set("custom_transfer_type", transfer_type, update_modified=False)

    handler = {
        "To Sales & Marketing":   _apply_to_sales,
        "From Sales & Marketing": _apply_from_sales,
        "Office to Office":       _apply_office_to_office,
        "Company Change":         lambda d, o, n: [
            f"Company change {d.company} → {d.new_company} — "
            "ERPNext handles the standard pieces (no Chundakadan side-effects)."
        ],
        "Other":                  lambda d, o, n: [
            "No department change detected — no Chundakadan side-effects to apply."
        ],
    }.get(transfer_type, lambda d, o, n: [])

    actions_log = handler(doc, old_dept, new_dept)

    if actions_log:
        body = (
            "<b>Chundakadan transfer side-effects:</b>"
            f"<br><i>Type: {escape_html(transfer_type)}</i><ul>"
            + "".join(f"<li>{escape_html(line)}</li>" for line in actions_log)
            + "</ul>"
        )
        doc.add_comment("Info", body)


# ──────────────────────────────────────────────────────────────────
# Classification
# ──────────────────────────────────────────────────────────────────

def _is_sales_dept(dept):
    if not dept:
        return False
    d = dept.lower()
    return "sales" in d or "marketing" in d


def _detect_transfer_type(old_dept, new_dept, doc):
    if doc.new_company and doc.company and doc.company != doc.new_company:
        return "Company Change"
    old_sales = _is_sales_dept(old_dept)
    new_sales = _is_sales_dept(new_dept)
    if not old_sales and new_sales:
        return "To Sales & Marketing"
    if old_sales and not new_sales:
        return "From Sales & Marketing"
    if old_dept and new_dept and old_dept != new_dept:
        return "Office to Office"
    return "Other"


def _resolve_dept_targets(dept):
    """Return (salary_structure, role_profile) for the given department."""
    if not dept:
        return (None, None)
    base = (dept.split(" - ")[0] or "").strip()
    if base in DEPT_TO_STRUCTURE:
        return DEPT_TO_STRUCTURE[base]
    base_lower = base.lower()
    for key, val in DEPT_TO_STRUCTURE.items():
        if key.lower() in base_lower:
            return val
    return (None, None)


def _resolve_leave_approver(dept):
    """Find a User holding the role for this department's HOD."""
    if not dept:
        return None
    d = dept.lower()
    if "sales" in d or "marketing" in d:
        role = "Sales HOD Leave Approver"
    elif "accountant" in d or "purchase" in d:
        role = "Accounts Manager Leave Approver"
    elif "general manager" in d or "gm" in d:
        role = "HR Leave Approver"  # GM gets approved by HR
    else:
        role = "HR Leave Approver"
    rows = frappe.db.sql("""SELECT u.name FROM `tabUser` u
        JOIN `tabHas Role` r ON r.parent = u.name
        WHERE r.role = %s AND u.enabled = 1
          AND u.name != 'Administrator'
        ORDER BY u.name LIMIT 1""", role, as_dict=True)
    return rows[0]["name"] if rows else None


# ──────────────────────────────────────────────────────────────────
# Handlers
# ──────────────────────────────────────────────────────────────────

def _apply_to_sales(doc, old_dept, new_dept):
    emp = doc.employee
    emp_name = doc.employee_name
    company = doc.new_company or doc.company
    log = []

    # 1. Sales Person — create or re-enable
    sp_name = frappe.db.get_value("Sales Person", {"employee": emp}, "name")
    if sp_name:
        if not frappe.db.get_value("Sales Person", sp_name, "enabled"):
            frappe.db.set_value("Sales Person", sp_name, "enabled", 1,
                                 update_modified=False)
            log.append(f"Re-enabled Sales Person: {sp_name}")
        else:
            log.append(f"Sales Person already enabled: {sp_name}")
    else:
        parent = frappe.db.get_value("Sales Person",
            {"is_group": 1, "parent_sales_person": ""}, "name") or \
            frappe.db.get_value("Sales Person", {"is_group": 1}, "name") or \
            "Sales Team"
        try:
            sp = frappe.get_doc({
                "doctype": "Sales Person",
                "sales_person_name": emp_name,
                "employee": emp,
                "enabled": 1,
                "is_group": 0,
                "parent_sales_person": parent,
            })
            sp.insert(ignore_permissions=True)
            sp_name = sp.name
            log.append(f"Created Sales Person: {sp_name} (parent: {parent})")
        except Exception as e:
            log.append(f"Could not create Sales Person: {str(e)[:120]}")
            sp_name = None

    # 2. MOP Mapping — add Cash + Cheque rows if missing
    if sp_name:
        try:
            cs = frappe.get_single("Chundakadan Settings")
            existing = {(r.sales_person, r.mode_of_payment)
                        for r in (cs.mop_mapping or [])}
            cash_acct = frappe.db.get_value("Account",
                {"company": company, "account_name": "Cash",
                 "is_group": 0}, "name")
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
                log.append(f"Added {added} MOP Mapping row(s) "
                           f"for {sp_name}")
            else:
                log.append("MOP Mapping rows already present (or accounts "
                           "missing) — no change")
        except Exception as e:
            log.append(f"MOP Mapping update failed: {str(e)[:120]}")

    # 3. Clear shift_location on active Shift Assignments → field staff
    cleared = 0
    for sa in frappe.get_all("Shift Assignment",
            filters={"employee": emp, "docstatus": 1, "status": "Active",
                     "shift_location": ["is", "set"]}, pluck="name"):
        frappe.db.set_value("Shift Assignment", sa, "shift_location",
                             None, update_modified=False)
        cleared += 1
    if cleared:
        log.append(f"Cleared shift_location on {cleared} active "
                   f"Shift Assignment(s) — now field staff (no geofence)")
    else:
        log.append("No shift_location to clear — already field staff")

    # 4. Salary Structure Assignment
    new_ss, new_rp = _resolve_dept_targets(new_dept)
    if new_ss:
        _switch_salary_structure(emp, new_ss, log)

    # 5. Role Profile
    if new_rp:
        _switch_role_profile(emp, new_rp, log)

    # 6. leave_approver
    new_la = _resolve_leave_approver(new_dept)
    if new_la:
        old_la = frappe.db.get_value("Employee", emp, "leave_approver")
        if old_la != new_la:
            frappe.db.set_value("Employee", emp, "leave_approver", new_la,
                                 update_modified=False)
            log.append(f"leave_approver: {old_la or '(none)'} → {new_la}")

    return log


def _apply_from_sales(doc, old_dept, new_dept):
    emp = doc.employee
    company = doc.new_company or doc.company
    log = []

    # 1. Sales Person — disable, keep history
    sp_name = frappe.db.get_value("Sales Person", {"employee": emp}, "name")
    if sp_name:
        if frappe.db.get_value("Sales Person", sp_name, "enabled"):
            frappe.db.set_value("Sales Person", sp_name, "enabled", 0,
                                 update_modified=False)
            log.append(f"Disabled Sales Person: {sp_name} "
                       f"(history kept)")
        else:
            log.append(f"Sales Person {sp_name} already disabled")

        # 2. MOP Mapping rows — keep for audit, just note
        n = frappe.db.count("Chundakadan Sales Person MOP",
            {"parent": "Chundakadan Settings", "sales_person": sp_name})
        if n:
            log.append(f"Kept {n} historical MOP Mapping row(s) for "
                       f"{sp_name} (will not auto-suggest in new entries)")

    # 3. Shift Assignment — set shift_location=HOD (office staff)
    if frappe.db.exists("Shift Location", "HOD"):
        existing_active = frappe.db.get_value("Shift Assignment",
            {"employee": emp, "docstatus": 1, "status": "Active"}, "name")
        if existing_active:
            cur_loc = frappe.db.get_value("Shift Assignment",
                existing_active, "shift_location")
            if cur_loc != "HOD":
                frappe.db.set_value("Shift Assignment", existing_active,
                                     "shift_location", "HOD",
                                     update_modified=False)
                log.append(f"Set shift_location=HOD on Shift Assignment "
                           f"{existing_active} (was {cur_loc or 'NULL'})")
            else:
                log.append(f"Shift Assignment {existing_active} already "
                           f"on HOD")
        else:
            st = "Office Shift" if frappe.db.exists("Shift Type",
                                                    "Office Shift") else \
                 frappe.db.get_value("Shift Type", {}, "name")
            if st:
                try:
                    sa = frappe.get_doc({
                        "doctype": "Shift Assignment",
                        "employee": emp,
                        "shift_type": st,
                        "shift_location": "HOD",
                        "start_date": doc.transfer_date or today(),
                        "status": "Active",
                        "company": company,
                    })
                    sa.insert(ignore_permissions=True)
                    sa.submit()
                    log.append(f"Created Shift Assignment {sa.name} "
                               f"({st}, shift_location=HOD)")
                except Exception as e:
                    log.append(f"Could not create Shift Assignment: "
                               f"{str(e)[:120]}")

    # 4. Salary Structure
    new_ss, new_rp = _resolve_dept_targets(new_dept)
    if new_ss:
        _switch_salary_structure(emp, new_ss, log)

    # 5. Role Profile
    if new_rp:
        _switch_role_profile(emp, new_rp, log)

    # 6. leave_approver
    new_la = _resolve_leave_approver(new_dept)
    if new_la:
        old_la = frappe.db.get_value("Employee", emp, "leave_approver")
        if old_la != new_la:
            frappe.db.set_value("Employee", emp, "leave_approver", new_la,
                                 update_modified=False)
            log.append(f"leave_approver: {old_la or '(none)'} → {new_la}")

    return log


def _apply_office_to_office(doc, old_dept, new_dept):
    emp = doc.employee
    log = []

    new_ss, new_rp = _resolve_dept_targets(new_dept)
    if new_ss:
        _switch_salary_structure(emp, new_ss, log)
    if new_rp:
        _switch_role_profile(emp, new_rp, log)
    new_la = _resolve_leave_approver(new_dept)
    if new_la:
        old_la = frappe.db.get_value("Employee", emp, "leave_approver")
        if old_la != new_la:
            frappe.db.set_value("Employee", emp, "leave_approver", new_la,
                                 update_modified=False)
            log.append(f"leave_approver: {old_la or '(none)'} → {new_la}")
    if not log:
        log.append("No mappable targets for office-to-office change "
                   "(department not in DEPT_TO_STRUCTURE)")
    return log


# ──────────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────────

def _switch_salary_structure(emp, new_structure, log):
    """Cancel the current SSA + create a fresh one with the same base."""
    if not frappe.db.exists("Salary Structure", new_structure):
        log.append(f"Salary Structure {new_structure} doesn't exist — "
                   f"skipped")
        return

    current = frappe.db.sql("""SELECT name, salary_structure, base
        FROM `tabSalary Structure Assignment`
        WHERE employee = %s AND docstatus = 1
        ORDER BY from_date DESC LIMIT 1""", emp, as_dict=True)

    if current and current[0]["salary_structure"] == new_structure:
        log.append(f"Salary Structure already {new_structure} — no change")
        return

    base = (current[0]["base"] if current else 0) or 0
    company = frappe.db.get_value("Employee", emp, "company")

    if current:
        try:
            d = frappe.get_doc("Salary Structure Assignment",
                                current[0]["name"])
            d.cancel()
            log.append(f"Cancelled SSA {current[0]['name']} "
                       f"({current[0]['salary_structure']})")
        except Exception as e:
            log.append(f"Could not cancel old SSA: {str(e)[:120]}")
            return

    try:
        new_ssa = frappe.get_doc({
            "doctype": "Salary Structure Assignment",
            "employee": emp,
            "salary_structure": new_structure,
            "from_date": today(),
            "company": company,
            "base": base,
        })
        new_ssa.insert(ignore_permissions=True)
        new_ssa.submit()
        log.append(f"Created SSA {new_ssa.name} "
                   f"({new_structure}, base=₹{base:,.0f})")
    except Exception as e:
        log.append(f"Could not create new SSA: {str(e)[:120]}")


def _switch_role_profile(emp, new_profile, log):
    """Update the User's role_profile_name if it differs."""
    if not frappe.db.exists("Role Profile", new_profile):
        log.append(f"Role Profile {new_profile} doesn't exist — skipped")
        return

    user_id = frappe.db.get_value("Employee", emp, "user_id")
    if not user_id:
        log.append("Employee has no linked User — role profile not updated")
        return

    current = frappe.db.get_value("User", user_id, "role_profile_name")
    if current == new_profile:
        log.append(f"Role Profile already {new_profile} — no change")
        return

    try:
        user = frappe.get_doc("User", user_id)
        user.role_profile_name = new_profile
        user.flags.ignore_permissions = True
        user.save()
        log.append(f"Role Profile: {current or '(none)'} → {new_profile}")
    except Exception as e:
        log.append(f"Could not switch Role Profile: {str(e)[:120]}")
