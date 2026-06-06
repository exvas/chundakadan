# Salary Slip hooks — enforce Chundakadan's payroll_basis setting.
#
# Wired in hooks.py as doc_events.Salary Slip.validate. Frappe runs
# the doctype controller's validate FIRST (HRMS computes working
# days, gross, net, etc.), then our hooks run after. So by the time
# we get here, HRMS has already set total_working_days from the
# holiday list / calendar. We override + recompute if Chundakadan
# Settings.payroll_basis = 'Fixed 30 Days'.

import frappe


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
