# Salary Slip hooks — enforce Chundakadan's payroll_basis setting.
#
# Wired in hooks.py as doc_events.Salary Slip.validate. Frappe runs
# the doctype controller's validate FIRST (HRMS computes working
# days, gross, net, etc.), then our hooks run after. So by the time
# we get here, HRMS has already set total_working_days from the
# holiday list / calendar. We override + recompute if Chundakadan
# Settings.payroll_basis = 'Fixed 30 Days'.

import frappe
from frappe.utils import flt, rounded, getdate

SICK_LEAVE_TYPE = "Sick Leave"
SICK_LEAVE_DEDUCTION = "Sick Leave Deduction"


def _sl_deduction_days(prior, m):
    """Deducted day-equivalents when adding `m` sick days on top of `prior`
    already taken this allocation-year. Graduated bands (cumulative):
      days  1-10 -> 0%   (full pay)
      days 11-20 -> 50%  deducted
      days 21-30 -> 75%  deducted
      days 31+   -> 100% deducted (SL exhausted)
    Handles fractional (half) days via band overlap. See unit tests.
    """
    prior = flt(prior)
    end = prior + flt(m)

    def overlap(a, b):
        return max(0.0, min(end, b) - max(prior, a))

    return 0.50 * overlap(10, 20) + 0.75 * overlap(20, 30) + 1.00 * overlap(30, 1e12)


def _sl_year_start(employee, start_date, end_date):
    """Start of the sick-leave counting year = the employee's SL Leave
    Allocation window covering this slip; falls back to calendar-year start."""
    alloc = frappe.db.sql(
        """select from_date from `tabLeave Allocation`
           where employee=%s and leave_type=%s and docstatus=1
             and from_date<=%s and to_date>=%s
           order by from_date desc limit 1""",
        (employee, SICK_LEAVE_TYPE, end_date, start_date),
    )
    if alloc:
        return getdate(alloc[0][0])
    return getdate(f"{getdate(start_date).year}-01-01")


def _sl_days_taken(employee, from_start, from_end):
    """Sick days from submitted Leave Applications whose START date is in
    [from_start, from_end] (inclusive), summed from the leave ledger (taken
    entries have negative `leaves`). Bucketing each spell by its start date
    means a boundary-spanning spell is counted once, in its start month —
    no double-count across slips, no missed days."""
    val = frappe.db.sql(
        """select ifnull(sum(leaves),0) from `tabLeave Ledger Entry`
           where employee=%s and leave_type=%s and transaction_type='Leave Application'
             and leaves<0 and from_date>=%s and from_date<=%s""",
        (employee, SICK_LEAVE_TYPE, from_start, from_end),
    )[0][0]
    return abs(flt(val))


def compute_sl_deduction(employee, start_date, end_date, gross):
    """Graduated sick-leave deduction for one slip. Reads the leave ledger
    only (m = SL spells starting this period; prior = spells starting earlier
    in the allocation year). Returns a dict for transparency/testing."""
    start_date, end_date = getdate(start_date), getdate(end_date)
    year_start = _sl_year_start(employee, start_date, end_date)
    m = _sl_days_taken(employee, start_date, end_date)
    if m <= 0 or flt(gross) <= 0:
        return {"prior": 0, "m": m, "ded_days": 0, "per_day": 0, "amount": 0}
    day_before = frappe.utils.add_days(start_date, -1)
    prior = _sl_days_taken(employee, year_start, day_before)
    ded_days = _sl_deduction_days(prior, m)
    per_day = flt(gross) / 30.0
    return {"prior": prior, "m": m, "ded_days": ded_days, "per_day": per_day,
            "amount": rounded(ded_days * per_day)}


def apply_payroll_basis(doc, method=None):
    """Enforce 'Fixed 30 Days' payroll basis per Najeeb's 2026-06-06 spec.

    For Fixed 30:
      - total_working_days = 30
      - payment_days = 30 - LWP - absent
      - Re-run HRMS's net-pay computation so earnings/deductions
        scale to the new 30-day base
    """
    basis = (
        frappe.db.get_single_value("Chundakadan Settings", "payroll_basis")
        or "Fixed 30 Days"
    )
    if basis != "Fixed 30 Days":
        return  # Calendar / Working Days → use HRMS default

    target_days = 30
    if doc.total_working_days == target_days:
        return  # already 30, nothing to do (idempotent for re-saves)

    # Override
    doc.total_working_days = target_days

    # payment_days = total - LOP days - unmarked absent
    lwp = float(doc.get("leave_without_pay") or 0)
    absent = float(doc.get("absent_days") or 0)
    doc.payment_days = max(target_days - lwp - absent, 0)

    # Re-run HRMS's net-pay calculation so earnings/deductions
    # scale to the new payment_days/total_working_days ratio.
    if hasattr(doc, "calculate_net_pay"):
        try:
            doc.calculate_net_pay()
        except Exception:
            # If the recalc fails (e.g., missing salary structure),
            # leave the override in place + let HRMS surface its
            # own error message.
            frappe.log_error(
                "chundakadan.doc_events.salary_slip: recalc failed",
                frappe.get_traceback(),
            )


def apply_sick_leave_deduction(doc, method=None):
    """Graduated Sick-Leave pay: 100%/50%/25% across cumulative sick days
    1-10 / 11-20 / 21-30 in the allocation-year (deduct the unpaid portion).

    Runs AFTER apply_payroll_basis so gross_pay + payment_days are settled.
    HRMS's calculate_net_pay rebuilds deductions from structure+Additional
    Salary and drops this injected row, so this always re-derives + re-adds it
    on every validate (self-healing), then recomputes totals manually (calling
    calculate_net_pay again would drop the row).
    """
    if not doc.employee or not doc.get("start_date"):
        return
    res = compute_sl_deduction(doc.employee, doc.start_date, doc.end_date, doc.gross_pay)
    amount = flt(res["amount"])

    # remove any prior Sick Leave Deduction row(s), then add fresh if >0
    existing = [d for d in (doc.get("deductions") or [])
                if d.salary_component == SICK_LEAVE_DEDUCTION]
    changed = False
    for d in existing:
        doc.remove(d)
        changed = True
    if amount > 0:
        if not frappe.db.exists("Salary Component", SICK_LEAVE_DEDUCTION):
            frappe.log_error(f"{SICK_LEAVE_DEDUCTION} component missing",
                             "chundakadan.salary_slip")
            return
        abbr = frappe.db.get_value("Salary Component", SICK_LEAVE_DEDUCTION,
                                   "salary_component_abbr")
        doc.append("deductions", {
            "salary_component": SICK_LEAVE_DEDUCTION, "abbr": abbr,
            "amount": amount, "default_amount": amount,
            "depends_on_payment_days": 0, "amount_based_on_formula": 0,
        })
        changed = True

    if not changed:
        return

    # recompute totals manually (do NOT call calculate_net_pay — it would drop
    # the injected row). Mirror HRMS: sum non-statistical, non-excluded rows.
    ded = sum(flt(d.amount) for d in (doc.get("deductions") or [])
              if not d.get("do_not_include_in_total") and not d.get("statistical_component"))
    doc.total_deduction = ded
    doc.base_total_deduction = ded
    doc.net_pay = flt(doc.gross_pay) - ded
    doc.base_net_pay = doc.net_pay
    doc.rounded_total = rounded(doc.net_pay)
    doc.base_rounded_total = doc.rounded_total
