# Copyright (c) 2026, Ashkar and contributors
# For license information, please see license.txt
"""Late Entry Deduction — per-minute salary deduction for late check-ins.

For each present day, an employee is "late" if their first IN check-in is past
``shift_start + late_entry_grace_period``. The minutes past that deadline are
priced at ``(SSA base / 30) / shift_duration_minutes`` and summed over the
period. The "Create Additional Salary" button posts one DRAFT Additional
Salary per employee (component "Late Arrival Deduction") for HR to submit.

See design: [[chundakadan-late-entry-deduction]].
"""
import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import flt, getdate, get_last_day

DAYS_IN_MONTH = 30          # chundakadan payroll_basis = Fixed 30 Days
LATE_COMPONENT = "Late Arrival Deduction"


def execute(filters=None):
    filters = frappe._dict(filters or {})
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 130},
        {"label": _("Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 190},
        {"label": _("Present Days"), "fieldname": "present_days", "fieldtype": "Int", "width": 110},
        {"label": _("Late Days"), "fieldname": "late_days", "fieldtype": "Int", "width": 95},
        {"label": _("Total Late Minutes"), "fieldname": "total_late_minutes", "fieldtype": "Int", "width": 145},
        {"label": _("Base"), "fieldname": "base", "fieldtype": "Currency", "width": 110},
        {"label": _("Deduction Amount"), "fieldname": "deduction_amount", "fieldtype": "Currency", "width": 150},
    ]


def _grace_and_duration():
    """{shift_name: (grace_minutes, duration_minutes)} from Shift Type."""
    out = {}
    for s in frappe.get_all("Shift Type", fields=["name", "start_time", "end_time", "late_entry_grace_period"]):
        dur = 0
        if s.start_time is not None and s.end_time is not None:
            dur = (s.end_time.total_seconds() - s.start_time.total_seconds()) / 60.0
            if dur < 0:  # overnight shift
                dur += 24 * 60
        out[s.name] = (int(s.late_entry_grace_period or 0), dur)
    return out


def _base_map(to_date, employee=None):
    """Latest submitted SSA base per employee effective on/before to_date."""
    cond = "and employee = %(emp)s" if employee else ""
    rows = frappe.db.sql(
        f"""
        select employee, base
        from `tabSalary Structure Assignment`
        where docstatus = 1 and from_date <= %(to)s {cond}
        order by employee, from_date desc, creation desc
        """,
        {"to": to_date, "emp": employee},
        as_dict=True,
    )
    base = {}
    for r in rows:                       # first row per employee wins (ordered desc)
        base.setdefault(r.employee, flt(r.base))
    return base


def _late_rows(filters):
    """First IN check-in per employee per day within the period, with shift info."""
    from_dt = getdate(filters.from_date)
    to_dt = getdate(filters.to_date)
    conds = ["ec.time >= %(from)s", "ec.time < %(to)s"]
    params = {"from": f"{from_dt} 00:00:00", "to": f"{to_dt} 23:59:59"}
    if filters.get("employee"):
        conds.append("ec.employee = %(employee)s")
        params["employee"] = filters.employee
    if filters.get("shift"):
        conds.append("ec.shift = %(shift)s")
        params["shift"] = filters.shift
    where = " and ".join(conds)
    # earliest IN per employee/day; ignore rows with no resolved shift start
    return frappe.db.sql(
        f"""
        select ec.employee, date(ec.time) as dt, min(ec.time) as first_in,
               ec.shift, ec.shift_start, ec.shift_end
        from `tabEmployee Checkin` ec
        where {where}
          and (ec.log_type = 'IN' or ec.log_type is null or ec.log_type = '')
          and ec.shift_start is not null
        group by ec.employee, date(ec.time), ec.shift, ec.shift_start, ec.shift_end
        """,
        params,
        as_dict=True,
    )


def get_data(filters):
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("Please select From Date and To Date."))

    shift_info = _grace_and_duration()
    base_map = _base_map(getdate(filters.to_date), filters.get("employee"))
    rows = _late_rows(filters)

    agg = {}
    for r in rows:
        grace, dur_from_type = shift_info.get(r.shift, (0, 0))
        deadline = r.shift_start + timedelta(minutes=grace)
        late_min = int(max(0.0, (r.first_in - deadline).total_seconds()) // 60)

        # duration: prefer the checkin's own shift window, else the Shift Type's
        dur = 0.0
        if r.shift_end:
            dur = (r.shift_end - r.shift_start).total_seconds() / 60.0
        if dur <= 0:
            dur = dur_from_type
        base = base_map.get(r.employee, 0.0)
        per_min = (base / DAYS_IN_MONTH) / dur if dur > 0 else 0.0

        a = agg.setdefault(r.employee, {"present_days": 0, "late_days": 0,
                                        "total_late_minutes": 0, "deduction": 0.0})
        a["present_days"] += 1
        if late_min > 0:
            a["late_days"] += 1
            a["total_late_minutes"] += late_min
            a["deduction"] += late_min * per_min

    names = {e.name: e.employee_name for e in frappe.get_all(
        "Employee", filters={"name": ["in", list(agg.keys())]} if agg else {"name": ["in", [""]]},
        fields=["name", "employee_name"])}

    data = []
    for emp, a in agg.items():
        if not a["total_late_minutes"]:
            continue  # only show employees who were actually late
        data.append({
            "employee": emp,
            "employee_name": names.get(emp, emp),
            "present_days": a["present_days"],
            "late_days": a["late_days"],
            "total_late_minutes": a["total_late_minutes"],
            "base": base_map.get(emp, 0.0),
            "deduction_amount": round(a["deduction"]),   # nearest rupee
        })
    data.sort(key=lambda d: d["deduction_amount"], reverse=True)
    return data


@frappe.whitelist()
def create_additional_salary(rows, from_date, to_date, payroll_date=None, company=None):
    """Post one DRAFT Additional Salary (Late Arrival Deduction) per row.

    Idempotent: an existing DRAFT for the same employee + component + period
    (ref = the period end payroll_date) is replaced so re-running updates the
    amount. Never touches a submitted Additional Salary.
    """
    if isinstance(rows, str):
        rows = json.loads(rows)
    if not frappe.db.exists("Salary Component", LATE_COMPONENT):
        frappe.throw(_("Salary Component '{0}' not found.").format(LATE_COMPONENT))

    pdate = getdate(payroll_date) if payroll_date else get_last_day(getdate(to_date))
    result = {"created": 0, "replaced": 0, "skipped": 0, "failed": 0, "errors": [], "docs": []}

    for row in rows:
        try:
            emp = row.get("employee")
            amount = flt(row.get("deduction_amount") or row.get("amount") or 0)
            if not emp or amount <= 0:
                result["skipped"] += 1
                continue
            emp_doc = frappe.get_doc("Employee", emp)
            comp = company or emp_doc.company

            existing = frappe.get_all("Additional Salary", filters={
                "employee": emp, "salary_component": LATE_COMPONENT,
                "payroll_date": pdate, "docstatus": 0,
            }, pluck="name")
            for name in existing:
                frappe.delete_doc("Additional Salary", name, ignore_permissions=True)

            doc = frappe.get_doc({
                "doctype": "Additional Salary",
                "employee": emp,
                "employee_name": emp_doc.employee_name,
                "company": comp,
                "salary_component": LATE_COMPONENT,
                "amount": amount,
                "payroll_date": pdate,
                "overwrite_salary_structure_amount": 0,
                "custom_reason": _("Late entry deduction {0} to {1}: {2} late min").format(
                    getdate(from_date), getdate(to_date), row.get("total_late_minutes") or ""),
            })
            doc.insert()          # DRAFT — HR submits before payroll
            result["replaced" if existing else "created"] += 1
            result["docs"].append(doc.name)
        except Exception as e:
            result["failed"] += 1
            result["errors"].append(f"{row.get('employee')}: {str(e)[:120]}")

    frappe.db.commit()
    return result
