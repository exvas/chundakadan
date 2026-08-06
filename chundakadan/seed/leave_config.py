# Canonical leave configuration for chundakadan (per the HR leave-policy table).
#
# 5 leave types + one Leave Policy, re-synced on every `bench migrate`
# (wired into before_migrate) so desk edits can't silently drift.
#
#   Casual Leave (CL)       paid   max 1/month (enforced in api/leave.py)   12/yr
#   Compassionate Leave     paid   max 1/month (enforced in api/leave.py)   12/yr
#   Compensatory Off        paid   is_compensatory=1 (earned via Comp req)  earned
#   Sick Leave (SL)         paid   graduated 100/50/25 (payroll)            30/yr
#   Leave Without Pay (LOP) unpaid is_lwp=1                                 on-demand
#
# Monthly cap = code (api/leave.py). Graduated SL pay = sub-project B.

import frappe

LEAVE_POLICY = "HR-LPOL-2026-00001"        # updated in place — keeps existing assignments

# (name, {field: value}) — only the fields we assert; others left as-is
LEAVE_TYPES = [
    ("Casual Leave",        {"is_lwp": 0, "is_compensatory": 0, "is_ppl": 0,
                             "include_holiday": 0, "max_continuous_days_allowed": 1}),
    ("Compassionate Leave", {"is_lwp": 0, "is_compensatory": 0, "is_ppl": 0,
                             "include_holiday": 0, "max_continuous_days_allowed": 3}),
    ("Compensatory Off",    {"is_lwp": 0, "is_compensatory": 1, "is_ppl": 0}),
    ("Sick Leave",          {"is_lwp": 0, "is_compensatory": 0, "is_ppl": 0}),
    ("Leave Without Pay",   {"is_lwp": 1, "is_compensatory": 0, "is_ppl": 0}),
]

# leave types no longer offered — removed from the policy (history preserved)
RETIRE_FROM_POLICY = ["Leave with pay", "Privilege Leave", "Compensatory"]

# annual allocations in the Leave Policy (Comp Off = earned, LOP = on-demand -> not listed)
POLICY_ALLOCATION = {
    "Casual Leave": 12,
    "Compassionate Leave": 12,
    "Sick Leave": 30,
}


def ensure_leave_types(*args, **kwargs):
    for name, fields in LEAVE_TYPES:
        if not frappe.db.exists("Leave Type", name):
            doc = frappe.new_doc("Leave Type")
            doc.leave_type_name = name
            for k, v in fields.items():
                doc.set(k, v)
            doc.insert(ignore_permissions=True)
            print(f"chundakadan.leave_config: created Leave Type {name}")
            continue
        doc = frappe.get_doc("Leave Type", name)
        changed = [k for k, v in fields.items() if (doc.get(k) or 0) != v]
        if changed:
            for k, v in fields.items():
                doc.set(k, v)
            doc.flags.ignore_permissions = True
            doc.save()
            print(f"chundakadan.leave_config: updated Leave Type {name} ({', '.join(changed)})")

    # delete the unused 'Compensatory' duplicate (superseded by Compensatory Off)
    if frappe.db.exists("Leave Type", "Compensatory"):
        used = (frappe.db.exists("Leave Application", {"leave_type": "Compensatory"})
                or frappe.db.exists("Leave Allocation", {"leave_type": "Compensatory"})
                or frappe.db.exists("Leave Ledger Entry", {"leave_type": "Compensatory"}))
        if not used:
            frappe.delete_doc("Leave Type", "Compensatory", ignore_permissions=True, force=1)
            print("chundakadan.leave_config: deleted unused Leave Type 'Compensatory'")


def ensure_leave_policy(*args, **kwargs):
    if not frappe.db.exists("Leave Policy", LEAVE_POLICY):
        return
    want = POLICY_ALLOCATION
    current = {d.leave_type: float(d.annual_allocation or 0)
              for d in frappe.get_all("Leave Policy Detail",
                                      filters={"parent": LEAVE_POLICY},
                                      fields=["leave_type", "annual_allocation"])}
    if set(current) == set(want) and all(not flt_ne(current[t], want[t]) for t in want):
        return
    # Leave Policy is a SUBMITTED doctype -> its detail table can't be changed
    # via save(); rewrite the child rows directly (they only drive allocation
    # amounts, not GL/ledger, so this is safe).
    frappe.db.delete("Leave Policy Detail", {"parent": LEAVE_POLICY})
    for idx, (lt, alloc) in enumerate(want.items(), start=1):
        frappe.get_doc({
            "doctype": "Leave Policy Detail", "parent": LEAVE_POLICY,
            "parenttype": "Leave Policy", "parentfield": "leave_policy_details",
            "idx": idx, "leave_type": lt, "annual_allocation": alloc,
        }).db_insert()
    frappe.clear_cache(doctype="Leave Policy")
    print(f"chundakadan.leave_config: updated Leave Policy {LEAVE_POLICY} -> {want}")


def flt_ne(a, b):
    return abs(float(a or 0) - float(b or 0)) > 0.001


def seed_leave_config(*args, **kwargs):
    """before_migrate entrypoint — idempotent."""
    ensure_leave_types()
    ensure_leave_policy()
