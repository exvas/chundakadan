# Auto-create Payroll Period for the current Indian financial year
# (Apr 1 → Mar 31). Idempotent — runs every migrate, no-op once the
# period exists.
#
# Why a Payroll Period: Frappe's Salary Slip + Payroll Entry filter by
# Payroll Period for annual reports (Salary Register, Payroll
# Statistics, etc.). Without one, monthly slips still work but
# year-level reports don't group correctly.
#
# Tax slabs are NOT seeded because chundakadan has no taxable employees
# (everyone earns below the ₹3L threshold). If that changes, add an
# Income Tax Slab manually in the desk.

import frappe
from frappe.utils import getdate, get_first_day, add_months


COMPANY = "Chundakadan Agencies"


def _current_fy_dates():
    """Return (start, end) of the Indian FY enclosing today.

    Indian FY runs Apr 1 → Mar 31. If today is Jan/Feb/Mar, we're in
    the FY that started LAST April.
    """
    today = getdate()
    if today.month >= 4:
        start = today.replace(month=4, day=1)
        end = today.replace(year=today.year + 1, month=3, day=31)
    else:
        start = today.replace(year=today.year - 1, month=4, day=1)
        end = today.replace(month=3, day=31)
    return start, end


def ensure_current_fy_period(*args, **kwargs):
    """Idempotent: create a Payroll Period for the current Indian FY
    if one doesn't already exist for this company.

    Wired as before_migrate so every deploy keeps the current FY
    available even when April rolls around.
    """
    if not frappe.db.exists("Company", COMPANY):
        return

    if not frappe.db.exists("DocType", "Payroll Period"):
        return

    start, end = _current_fy_dates()
    period_name = f"FY {start.year}-{str(end.year)[-2:]}"

    # Already exists for this company + date range?
    existing = frappe.get_all(
        "Payroll Period",
        filters={
            "company": COMPANY,
            "start_date": str(start),
            "end_date": str(end),
        },
        pluck="name",
        ignore_permissions=True,
    )
    if existing:
        return

    try:
        doc = frappe.get_doc({
            "doctype": "Payroll Period",
            "company": COMPANY,
            "name": period_name,
            "start_date": str(start),
            "end_date": str(end),
        })
        doc.flags.ignore_permissions = True
        doc.insert()
        frappe.db.commit()
        print(f"chundakadan.seed.payroll_period: created '{period_name}' "
              f"({start} → {end}) for {COMPANY}")
    except Exception as e:
        print(f"chundakadan.seed.payroll_period: could not create period: {e}")
