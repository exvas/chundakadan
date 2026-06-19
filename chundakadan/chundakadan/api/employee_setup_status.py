# Copyright (c) 2026, Ashkar and contributors
# For license information, please see license.txt

"""Setup-completeness check for the Employee form.

Renders a "what's missing" checklist at the top of every Employee page so
HR can see at a glance whether the standard onboarding items have been
done — and click straight through to fix what's pending.

Tracked items (in order of priority):
  1. User Account              (Employee.user_id set)
  2. Leave Allocation          (active in current FY)
  3. Leave Policy Assignment   (submitted)
  4. Shift Assignment          (active, submitted)
  5. Salary Structure Assignment (submitted)
  6. Reports To                (optional but flagged)

Each item returns {ok, label, fix_hint, fix_url}. The JS renders pending
items as a yellow banner with clickable fix links.
"""

import frappe
from frappe import _
from frappe.utils import getdate, nowdate, get_fullname


@frappe.whitelist()
def get_setup_status(employee):
    """Return a list of setup-check dicts for the given Employee.
    Used by employee.js to render the pending-setup banner."""
    emp = frappe.get_doc("Employee", employee)
    today = nowdate()
    checks = []

    # 1. User Account
    checks.append({
        "key": "user_account",
        "label": _("User Account"),
        "ok": bool(emp.user_id),
        "value": emp.user_id or "",
        "fix_hint": _("Click HR Actions → Create User & Setup"),
        "fix_url": None,
    })

    # 1b. User Permissions — only check if user_id is set. The expected
    # set differs by role (manager / HR / GM don't get Employee=self;
    # multi-company benches add a Company restriction). Re-uses the same
    # decision logic as create_user_for_employee so the banner stays in
    # sync with what Create User would actually apply.
    if emp.user_id:
        from chundakadan.chundakadan.api.employee_user_actions import (
            _should_restrict_to_self,
        )
        needs_employee_perm = _should_restrict_to_self(emp)
        has_employee_perm = bool(frappe.db.exists("User Permission", {
            "user": emp.user_id, "allow": "Employee", "for_value": emp.name,
        }))
        n_companies = frappe.db.count("Company")
        needs_company_perm = bool(emp.company and n_companies > 1)
        has_company_perm = bool(emp.company and frappe.db.exists("User Permission", {
            "user": emp.user_id, "allow": "Company", "for_value": emp.company,
        }))
        ok = (
            (not needs_employee_perm or has_employee_perm)
            and (not needs_company_perm or has_company_perm)
        )
        # Describe what's expected so HR knows WHY it's flagged
        expected = []
        if needs_employee_perm: expected.append(f"Employee={emp.name}")
        if needs_company_perm:  expected.append(f"Company={emp.company}")
        if not expected:        expected.append("none (manager/HR in single-company bench)")
        checks.append({
            "key": "user_permissions",
            "label": _("User Permissions"),
            "ok": ok,
            "value": ", ".join(expected) if ok else "missing",
            "fix_hint": _("Re-run HR Actions → Create User & Setup (or add manually)"),
            "fix_url": f"/app/user-permission?user={emp.user_id}",
        })

    # 2. Leave Allocation — at least one active allocation covering today
    has_alloc = frappe.db.exists("Leave Allocation", {
        "employee": employee,
        "docstatus": 1,
        "from_date": ["<=", today],
        "to_date": [">=", today],
    })
    checks.append({
        "key": "leave_allocation",
        "label": _("Leave Allocation (this year)"),
        "ok": bool(has_alloc),
        "value": "",
        "fix_hint": _("Click HR Actions → Allocate Annual Leaves"),
        "fix_url": f"/app/leave-allocation/new?employee={employee}",
    })

    # 3. Leave Policy Assignment
    has_lpa = frappe.db.exists("Leave Policy Assignment", {
        "employee": employee,
        "docstatus": 1,
    })
    checks.append({
        "key": "leave_policy",
        "label": _("Leave Policy Assignment"),
        "ok": bool(has_lpa),
        "value": "",
        "fix_hint": _("Create a Leave Policy Assignment"),
        "fix_url": f"/app/leave-policy-assignment/new?employee={employee}",
    })

    # 4. Shift Assignment — active + submitted
    has_shift = frappe.db.exists("Shift Assignment", {
        "employee": employee,
        "docstatus": 1,
        "status": "Active",
    })
    checks.append({
        "key": "shift_assignment",
        "label": _("Shift Assignment"),
        "ok": bool(has_shift),
        "value": "",
        "fix_hint": _("Assign a shift (sets geofence for office staff)"),
        "fix_url": f"/app/shift-assignment/new?employee={employee}",
    })

    # 5. Salary Structure Assignment
    ssa = frappe.db.get_value("Salary Structure Assignment",
        {"employee": employee, "docstatus": 1},
        ["name", "salary_structure"], as_dict=True, order_by="from_date desc")
    checks.append({
        "key": "salary_structure",
        "label": _("Salary Structure Assignment"),
        "ok": bool(ssa),
        "value": (ssa.salary_structure if ssa else ""),
        "fix_hint": _("Assign a salary structure"),
        "fix_url": f"/app/salary-structure-assignment/new?employee={employee}",
    })

    # 6. Reports To (optional but flagged)
    checks.append({
        "key": "reports_to",
        "label": _("Reports To"),
        "ok": bool(emp.reports_to),
        "value": emp.reports_to or "",
        "fix_hint": _("Set the reporting manager on the Joining tab"),
        "fix_url": None,
        "optional": True,
    })

    return {
        "employee": employee,
        "employee_name": emp.employee_name,
        "status": emp.status,
        "checks": checks,
        "total": len(checks),
        "complete": sum(1 for c in checks if c["ok"]),
        "pending": sum(1 for c in checks if not c["ok"]),
        "pending_required": sum(1 for c in checks if not c["ok"] and not c.get("optional")),
    }


@frappe.whitelist()
def get_setup_status_bulk(employees):
    """Bulk version for list-view indicators. Takes a JSON list of
    employee names, returns {employee: pending_required_count}."""
    import json
    if isinstance(employees, str):
        employees = json.loads(employees)
    out = {}
    for emp in employees:
        try:
            r = get_setup_status(emp)
            out[emp] = r["pending_required"]
        except Exception:
            out[emp] = -1   # error fetching
    return out
