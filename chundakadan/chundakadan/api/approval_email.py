"""Shared email-notification sender for the multi-step approval workflows.

Called from chundakadan.api.expense_approval and chundakadan.api.leave at
the four workflow events. Uses a single Jinja template
(chundakadan/templates/emails/approval_notification.html) that branches on
the `event` variable for layout.

Outbound goes through Frappe's standard `frappe.sendmail()` which respects
the default Email Domain on this site (gmail.com → notify.chundakadan@gmail.com).
"""
from __future__ import annotations

import frappe
from frappe.utils import flt, fmt_money, format_date


# Map doctype → URL slug for the deep link in the CTA
_DOCTYPE_SLUG = {
    "Leave Application": "leave-application",
    "Expense Claim": "expense-claim",
    "Employee Advance": "employee-advance",
    "Payment Request": "payment-request",
    "Office Expense Voucher": "office-expense-voucher",
}


# Per-doctype config: how to pull the "amount" field for display
_AMOUNT_FIELD = {
    "Expense Claim": ("total_claimed_amount", "currency"),
    "Employee Advance": ("advance_amount", "currency"),
    "Payment Request": ("grand_total", "currency"),
    "Office Expense Voucher": ("grand_total", None),  # OEV uses company default
    # Leave Application doesn't have an amount; we'll show days instead
}


def _site_url() -> str:
    """Best-effort site URL for the CTA link."""
    return (
        frappe.utils.get_url()
        or frappe.local.conf.get("hostname")
        or "https://erp.chundakadan.in"
    ).rstrip("/")


def _logo_url() -> str:
    url = frappe.db.get_single_value("Website Settings", "app_logo") \
        or "/files/CDN.png"
    if url.startswith("http"):
        return url
    return f"{_site_url()}{url}"


def _applicant(doc) -> tuple[str | None, str]:
    """Return (applicant_user_email, applicant_full_name)."""
    if doc.doctype == "Payment Request":
        # Payment Request — applicant is the doc owner (creator)
        owner_email = doc.get("owner") or frappe.session.user
        full = frappe.db.get_value("User", owner_email, "full_name") \
               or owner_email
        return owner_email, full

    employee = doc.get("employee")
    if not employee:
        return None, doc.get("owner") or ""
    emp_fields = frappe.db.get_value(
        "Employee", employee,
        ["user_id", "employee_name", "personal_email", "company_email"],
        as_dict=True,
    ) or {}
    email = (
        emp_fields.get("user_id")
        or emp_fields.get("company_email")
        or emp_fields.get("personal_email")
    )
    name = emp_fields.get("employee_name") or employee
    return email, name


def _full_name(email: str | None) -> str:
    if not email:
        return ""
    return frappe.db.get_value("User", email, "full_name") or email.split("@")[0]


def _amount_label(doc) -> str | None:
    if doc.doctype == "Leave Application":
        # Show "N days" instead of a money figure
        days = doc.get("total_leave_days")
        if days:
            return f"{flt(days):g} day{'s' if flt(days) != 1 else ''}"
        return None
    cfg = _AMOUNT_FIELD.get(doc.doctype)
    if not cfg:
        return None
    amount_field, currency_field = cfg
    amount = flt(doc.get(amount_field))
    if not amount:
        return None
    if currency_field:
        currency = doc.get(currency_field) or "INR"
    elif doc.get("company"):
        currency = frappe.db.get_value("Company", doc.get("company"),
                                        "default_currency") or "INR"
    else:
        currency = "INR"
    return fmt_money(amount, currency=currency)


def _approval_flow_for_template(doc) -> list[dict]:
    rows = doc.get("approval_flow") or []
    out = []
    for r in rows:
        approved_on = r.approved_on if hasattr(r, "approved_on") else r.get("approved_on")
        try:
            approved_on = format_date(approved_on, "dd-MMM-yyyy HH:mm") if approved_on else None
        except Exception:
            approved_on = str(approved_on) if approved_on else None
        out.append({
            "role": r.approver_role if hasattr(r, "approver_role") else r.get("approver_role"),
            "approver": r.approver if hasattr(r, "approver") else r.get("approver"),
            "status": r.status if hasattr(r, "status") else r.get("status"),
            "approved_on": approved_on,
            "remarks": r.remarks if hasattr(r, "remarks") else r.get("remarks"),
        })
    return out


def send_approval_email(
    doc,
    event: str,
    recipient_email: str,
    reject_remarks: str | None = None,
) -> None:
    """Send one approval notification email.

    event ∈ {"created", "advanced", "approved", "rejected"}
    recipient_email — who gets the email (approver or applicant)
    """
    if not recipient_email:
        return  # nothing to send to
    if event not in ("created", "advanced", "approved", "rejected"):
        return

    # Self-notification guard: don't email someone about their own action.
    # (Caller is responsible for picking the right recipient; this is a safety net.)
    acting_user = frappe.session.user
    if recipient_email == acting_user and event in ("approved", "rejected"):
        # When the applicant happens to be the same as the final approver,
        # still send so they have an audit trail.
        pass

    applicant_email, applicant_name = _applicant(doc)
    slug = _DOCTYPE_SLUG.get(doc.doctype, doc.doctype.lower().replace(" ", "-"))

    context = {
        "event": event,
        "doctype_label": doc.doctype,
        "doctype_slug": slug,
        "doc": doc,
        "applicant_name": applicant_name,
        "amount_label": _amount_label(doc),
        "recipient_name": _full_name(recipient_email),
        "current_approver": doc.get("current_approver"),
        "approval_flow": _approval_flow_for_template(doc),
        "reject_remarks": reject_remarks,
        "site_url": _site_url(),
        "logo_url": _logo_url(),
    }

    subject_map = {
        "created":  f"Action needed: review {doc.doctype} {doc.name} from {applicant_name}",
        "advanced": f"Final approval needed: {doc.doctype} {doc.name}",
        "approved": f"Your {doc.doctype} {doc.name} was approved",
        "rejected": f"Your {doc.doctype} {doc.name} was rejected",
    }

    try:
        html = frappe.render_template(
            "chundakadan/templates/emails/approval_notification.html",
            context,
        )
    except Exception as e:
        frappe.log_error(
            f"approval_email template render failed for {doc.doctype} {doc.name}: {e}",
            "approval_email render",
        )
        return

    try:
        frappe.sendmail(
            recipients=[recipient_email],
            subject=subject_map[event],
            message=html,
            reference_doctype=doc.doctype,
            reference_name=doc.name,
            now=False,  # queued — outbound worker will deliver
            expose_recipients="header",
        )
    except Exception as e:
        # Never break the workflow because email failed
        frappe.log_error(
            f"sendmail failed for {doc.doctype} {doc.name} ({event}) → {recipient_email}: {e}",
            "approval_email send",
        )


# --- Public entry points for the workflows ---------------------------

def notify_created(doc, method=None):
    """`after_insert` hook target. Email the first approver."""
    if doc.doctype not in _DOCTYPE_SLUG:
        return
    # Use current_approver if our chain set it (Expense / EA / PR);
    # Leave Application's leave.py sets the same field.
    recipient = doc.get("current_approver")
    if not recipient:
        return
    send_approval_email(doc, "created", recipient)


def notify_advanced(doc, next_approver: str):
    """Called from approve() when the chain advances to the next step."""
    send_approval_email(doc, "advanced", next_approver)


def notify_approved(doc):
    """Called from approve() after the final step. Emails applicant."""
    applicant_email, _ = _applicant(doc)
    if applicant_email:
        send_approval_email(doc, "approved", applicant_email)


def notify_rejected(doc, remarks: str | None = None):
    """Called from reject(). Emails applicant with the reason."""
    applicant_email, _ = _applicant(doc)
    if applicant_email:
        send_approval_email(doc, "rejected", applicant_email, reject_remarks=remarks)
