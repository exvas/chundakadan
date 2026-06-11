"""Office Expense Voucher (multi-line, direct-payment)

Books utility / office / petty expenses with one-or-more expense lines.

Posting modes (decided per-voucher by which field the user fills):

  A) PAID FROM filled (typical case)
     → Dr each expense line account (+ tax accounts)
     → Cr Paid From (Bank / Cash / Employee Payable when reimbursable)
     Single-step booking + payment. No outstanding. status='Paid'.

  B) PAYABLE ACCOUNT filled, PAID FROM blank (deferred)
     → Dr each expense line account (+ tax accounts)
     → Cr Payable Account
     Outstanding tracked. status='Unpaid'. Settle via Make Payment.

The Payable Account is a plain Liability account WITHOUT
account_type='Payable' — keeps these out of the standard Accounts
Payable / Aging reports (which only show party-based payables).
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt
from erpnext.controllers.accounts_controller import AccountsController
from erpnext.accounts.general_ledger import (
    make_gl_entries,
    make_reverse_gl_entries,
)
from chundakadan.install import get_oev_defaults_for_company


class OfficeExpenseVoucher(AccountsController):
    """Multi-line, direct-payment expense voucher."""

    # --- Validation ---------------------------------------------------

    def validate(self):
        self._autofill_from_settings()
        self._autofill_currency()
        self._validate_items()
        self._compute_totals()
        self._validate_payment_target()
        self._set_status_pre_submit()

    def outstanding_amount_field(self):
        """OEV doesn't store outstanding_amount as a column on the form
        (we removed it from the layout). Track via GL Entry sums on the
        Payable account if needed for deferred mode."""
        return None

    def _set_initial_outstanding(self):
        # No-op for now — outstanding lives in GL Entries against the
        # voucher when payable_account is used.
        pass

    def _autofill_from_settings(self):
        """Fill payable_account + per-line cost_center from the
        per-company Chundakadan Settings row matching this voucher's
        company.

        paid_from is INTENTIONALLY not server-filled — client JS fills
        it on new docs only, so clearing it to switch to deferred mode
        doesn't get auto-undone.
        """
        defaults = get_oev_defaults_for_company(self.company)

        if not self.payable_account and defaults.get("payable_account"):
            self.payable_account = defaults["payable_account"]

        cc_default = defaults.get("cost_center") or \
            (self.company and frappe.get_cached_value(
                "Company", self.company, "cost_center"))
        if not cc_default and self.company:
            cc_default = frappe.db.get_value(
                "Cost Center",
                {"company": self.company, "is_group": 0, "disabled": 0},
                "name",
            )
        if cc_default:
            for row in (self.items or []):
                if not row.cost_center:
                    row.cost_center = cc_default

    @property
    def is_reimbursable(self):
        # Backward-compat shim — the field was removed from the form
        # but a few code paths still reference it. Always False now.
        return 0

    def _autofill_currency(self):
        # Defensive — the doctype JSON may or may not carry currency
        # / exchange_rate fields depending on the active layout.
        if self.meta.has_field("currency") and not self.get("currency") \
                and self.company:
            self.currency = frappe.get_cached_value(
                "Company", self.company, "default_currency")
        if self.meta.has_field("exchange_rate") and not self.get("exchange_rate"):
            self.exchange_rate = 1.0

    def _validate_items(self):
        if not self.items:
            frappe.throw(_("At least one expense line is required."))
        for row in self.items:
            if not row.expense_account:
                frappe.throw(_("Row {0}: Expense Account is required.")
                             .format(row.idx))
            rt = frappe.db.get_value(
                "Account", row.expense_account, "root_type")
            if rt != "Expense":
                frappe.throw(_(
                    "Row {0}: Account {1} is not an Expense account (root_type={2})."
                ).format(row.idx, row.expense_account, rt))
            if flt(row.amount) <= 0:
                frappe.throw(_(
                    "Row {0}: Amount must be greater than zero."
                ).format(row.idx))

    def _compute_totals(self):
        subtotal = sum(flt(r.amount) for r in (self.items or []))
        total_tax = sum(flt(r.tax_amount) for r in (self.items or []))
        self.subtotal = subtotal
        self.total_tax = total_tax
        self.grand_total = subtotal + total_tax

    def _validate_payment_target(self):
        """At least one of Paid From / Payable Account must be set.
        BOTH can be set together — that triggers a 4-leg passthrough
        GL (Dr Expense → Cr Payable → Dr Payable → Cr Bank)."""
        if not self.paid_from and not self.payable_account:
            frappe.throw(_(
                "Pick <b>Paid From</b> (Bank / Cash), <b>Payable Account</b>, "
                "or both. Set defaults in Chundakadan Settings so they "
                "auto-fill on new vouchers."))

    def _set_status_pre_submit(self):
        if self.docstatus == 2:
            self.status = "Cancelled"
            return
        if self.docstatus == 0:
            cas = self.custom_approval_status
            if cas == "Rejected":
                self.status = "Rejected"
            elif cas == "Approved":
                self.status = "Approved"
            elif cas == "Partially Approved":
                self.status = "Partially Approved"
            elif cas == "Pending":
                self.status = "Pending Approval"
            else:
                self.status = "Draft"

    # --- Submit / Cancel ---------------------------------------------

    def on_submit(self):
        # Defensive invariant — submit can only happen via the approval
        # workflow, which sets cas='Approved'. If anything bypasses that,
        # force the state to match.
        if self.custom_approval_status != "Approved":
            self.custom_approval_status = "Approved"
            self.current_approver = None
            for row in (self.approval_flow or []):
                if row.status == "Pending":
                    row.status = "Approved"
                    row.approved_on = frappe.utils.now()
                    break
            self.db_set("custom_approval_status", "Approved",
                        update_modified=False)
            self.db_set("current_approver", None, update_modified=False)

        self.make_gl_entries()
        self.set_status(update=True)

    def on_cancel(self):
        # Tell Frappe's check_if_doc_is_linked to skip these doctypes
        # for any subsequent link check fired during this cancel
        # transaction. Set as INSTANCE attribute (not class) — Frappe's
        # doc.get('ignore_linked_doctypes') only reads instance __dict__,
        # not class attributes. Mirrors how ERPNext Sales/Purchase
        # Invoice handle the same problem.
        self.ignore_linked_doctypes = (
            "GL Entry",
            "Payment Ledger Entry",
            "Repost Payment Ledger",
            "Repost Payment Ledger Items",
            "Repost Accounting Ledger",
            "Repost Accounting Ledger Items",
        )
        make_reverse_gl_entries(
            voucher_type=self.doctype, voucher_no=self.name)
        self.set_status(update=True)

    # --- GL Entry construction ---------------------------------------

    def make_gl_entries(self, gl_entries=None, from_repost=False):
        gl_entries = gl_entries or self.get_gl_entries()
        if not gl_entries:
            return
        make_gl_entries(
            gl_entries,
            cancel=(self.docstatus == 2),
            update_outstanding="No",  # outstanding tracked via GL sums when needed
            merge_entries=False,
        )

    def get_gl_entries(self) -> list[dict]:
        """Build the GL entry rows.

        Posting shapes (decided by which fields the user filled):

        A) Paid From + Payable Account BOTH set → 4-leg passthrough:
           Dr Expense                       (per line)
              Cr Payable Account     (sum)
           Dr Payable Account                (clearing)
              Cr Paid From          (sum)

        B) Only Paid From set → direct 2-leg:
           Dr Expense (per line) / Cr Paid From

        C) Only Payable Account set → deferred 2-leg:
           Dr Expense (per line) / Cr Payable (outstanding)

        D) Reimbursable to Employee → employee payable:
           Dr Expense (per line) / Cr Employee Advance (party=Employee)
        """
        company_currency = frappe.get_cached_value(
            "Company", self.company, "default_currency")
        gl: list[dict] = []
        cr_cc_fallback = (self.items[0].cost_center if self.items else None) \
            or self._fallback_cost_center()

        # 1. Debits — one row per expense line (tax folded into expense
        # account for non-recoverable case).
        for row in (self.items or []):
            cc = row.cost_center or self._fallback_cost_center()
            line_dr = flt(row.amount) + flt(row.tax_amount)
            if line_dr <= 0:
                continue
            gl.append(self.get_gl_dict({
                "account": row.expense_account,
                "against": self._against_account(),
                "debit": line_dr,
                "credit": 0,
                "debit_in_account_currency": line_dr,
                "credit_in_account_currency": 0,
                "cost_center": cc,
                "against_voucher_type": self.doctype,
                "against_voucher": self.name,
                "remarks": row.description or self.description or "",
            }, account_currency=company_currency, item=self))

        # 2/3. Credit side
        if self.paid_from and self.payable_account:
            # ====== Shape A: 4-leg passthrough through Payable ======
            # Cr Payable (booking)
            gl.append(self.get_gl_dict({
                "account": self.payable_account,
                "against": (self.items[0].expense_account if self.items else ""),
                "debit": 0,
                "credit": flt(self.grand_total),
                "debit_in_account_currency": 0,
                "credit_in_account_currency": flt(self.grand_total),
                "cost_center": cr_cc_fallback,
                "against_voucher_type": self.doctype,
                "against_voucher": self.name,
                "remarks": self.description or self.vendor_payee or "",
            }, account_currency=company_currency, item=self))
            # Dr Payable (clearing)
            gl.append(self.get_gl_dict({
                "account": self.payable_account,
                "against": self.paid_from,
                "debit": flt(self.grand_total),
                "credit": 0,
                "debit_in_account_currency": flt(self.grand_total),
                "credit_in_account_currency": 0,
                "cost_center": cr_cc_fallback,
                "against_voucher_type": self.doctype,
                "against_voucher": self.name,
                "remarks": self.description or self.vendor_payee or "",
            }, account_currency=company_currency, item=self))
            # Cr Paid From (money out)
            gl.append(self.get_gl_dict({
                "account": self.paid_from,
                "against": self.payable_account,
                "debit": 0,
                "credit": flt(self.grand_total),
                "debit_in_account_currency": 0,
                "credit_in_account_currency": flt(self.grand_total),
                "cost_center": cr_cc_fallback,
                "against_voucher_type": self.doctype,
                "against_voucher": self.name,
                "remarks": self.description or self.vendor_payee or "",
            }, account_currency=company_currency, item=self))
        else:
            # ====== Shapes B / C / D: single Cr leg ======
            cr_account, party_type, party = self._credit_target()
            if not cr_account:
                frappe.throw(_("Could not resolve credit account."))
            cr_dict = {
                "account": cr_account,
                "against": (self.items[0].expense_account if self.items else ""),
                "debit": 0,
                "credit": flt(self.grand_total),
                "debit_in_account_currency": 0,
                "credit_in_account_currency": flt(self.grand_total),
                "cost_center": cr_cc_fallback,
                "against_voucher_type": self.doctype,
                "against_voucher": self.name,
                "remarks": self.description or self.vendor_payee or "",
            }
            if party_type and party:
                cr_dict["party_type"] = party_type
                cr_dict["party"] = party
            gl.append(self.get_gl_dict(
                cr_dict, account_currency=company_currency, item=self))

        return gl

    def _credit_target(self) -> tuple[str | None, str | None, str | None]:
        """Returns (account, party_type, party) for the Cr leg.

        Priority:
          1. paid_from filled → Bank / Cash (no party)
          2. payable_account filled → Payable account (no party if type != Payable)
        """
        if self.paid_from:
            atype = frappe.db.get_value("Account", self.paid_from, "account_type")
            # Bank/Cash accounts don't need party
            return (self.paid_from, None, None)

        if self.payable_account:
            atype = frappe.db.get_value(
                "Account", self.payable_account, "account_type") or ""
            # If user picked a 'Payable' typed account we'd need a party.
            # Our default Chundakadan setting points at an account_type=''
            # liability, so this is fine. But guard anyway.
            if atype == "Payable":
                # User picked a real Payable account — won't post without party.
                frappe.throw(_(
                    "Payable Account {0} has account_type='Payable' which "
                    "requires a Supplier. Use a Liability-type account "
                    "without 'Payable' type for Office Expense Vouchers, "
                    "or pick a Paid From bank/cash account instead."
                ).format(self.payable_account))
            return (self.payable_account, None, None)

        return (None, None, None)

    def _against_account(self) -> str:
        """Describes the Cr side on Dr GL rows (free-text narrative)."""
        if self.paid_from:
            return self.paid_from
        if self.payable_account:
            return self.payable_account
        return self.vendor_payee or ""

    def _fallback_cost_center(self) -> str | None:
        if hasattr(self, "_cached_cc"):
            return self._cached_cc
        # Priority: Company.cost_center → per-company Chundakadan defaults
        #           → first non-group cost center for the company
        cc = None
        if self.company:
            cc = frappe.get_cached_value("Company", self.company, "cost_center")
        if not cc:
            cc = get_oev_defaults_for_company(self.company).get("cost_center")
        if not cc and self.company:
            cc = frappe.db.get_value(
                "Cost Center",
                {"company": self.company, "is_group": 0, "disabled": 0},
                "name",
            )
        self._cached_cc = cc
        return cc

    # --- Status ------------------------------------------------------

    def set_status(self, update=False, status=None, update_modified=True):
        if self.is_new():
            return
        if not status:
            if self.docstatus == 2:
                status = "Cancelled"
            elif self.docstatus == 0:
                return  # draft / approval-pipeline statuses set elsewhere
            else:
                # Submitted = workflow approval is complete (the submit-guard
                # ensures cas='Approved' before submit). Show "Approved"
                # except for the deferred-only case where the payable hasn't
                # been cleared yet (paid_from blank, payable_account set).
                deferred_only = (self.payable_account and not self.paid_from)
                status = "Unpaid" if deferred_only else "Approved"
        self.status = status
        if update:
            self.db_set("status", status, update_modified=update_modified)


# --- Module utilities -----------------------------------------------

@frappe.whitelist()
def get_company_defaults(company: str) -> dict:
    """Return Chundakadan Settings → oev_defaults row matching `company`,
    augmented with Company.cost_center as a stronger cost_center default."""
    defaults = get_oev_defaults_for_company(company) or {}
    # Prefer Company.cost_center if not explicitly overridden in the table
    if not defaults.get("cost_center") and company:
        defaults["cost_center"] = frappe.get_cached_value(
            "Company", company, "cost_center")
    return defaults


@frappe.whitelist()
def make_payment_entry(source_name: str) -> dict:
    """Build a Payment Entry for the deferred-payment case (payable_account
    used, paid_from blank). Pre-fills enough that user just picks the bank.
    """
    source = frappe.get_doc("Office Expense Voucher", source_name)
    if source.docstatus != 1:
        frappe.throw(_("Voucher must be submitted before paying."))
    if source.paid_from:
        frappe.throw(_(
            "This voucher was already paid via {0}. "
            "No further Payment Entry needed.").format(source.paid_from))
    if not source.payable_account:
        frappe.throw(_(
            "No Payable Account set — voucher posting state is invalid."))

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Pay"
    pe.posting_date = frappe.utils.nowdate()
    pe.company = source.company
    pe.paid_to = source.payable_account
    pe.paid_to_account_currency = frappe.get_cached_value(
        "Account", source.payable_account, "account_currency") or \
        frappe.get_cached_value("Company", source.company, "default_currency")
    pe.paid_amount = flt(source.grand_total)
    pe.received_amount = flt(source.grand_total)
    pe.target_exchange_rate = 1.0
    pe.source_exchange_rate = 1.0
    pe.reference_no = source.reference_no or source.name
    pe.reference_date = source.reference_date or source.posting_date

    pe.append("references", {
        "reference_doctype": source.doctype,
        "reference_name": source.name,
        "due_date": source.posting_date,
        "total_amount": flt(source.grand_total),
        "outstanding_amount": flt(source.grand_total),
        "allocated_amount": flt(source.grand_total),
    })
    return pe.as_dict()


def update_voucher_status_on_payment(payment_doc, method=None):
    """When a PE referencing an OEV is submitted/cancelled, flip the
    voucher's status (paid_from-based vouchers were already 'Paid'
    on submit; this handles the deferred-payment / payable_account case)."""
    if not payment_doc.references:
        return
    refs = [
        r for r in payment_doc.references
        if r.reference_doctype == "Office Expense Voucher" and r.reference_name
    ]
    if not refs:
        return
    for ref in refs:
        try:
            voucher = frappe.get_doc("Office Expense Voucher", ref.reference_name)
            if voucher.docstatus != 1:
                continue
            new_status = "Paid" if payment_doc.docstatus == 1 else "Unpaid"
            voucher.db_set("status", new_status, update_modified=False)
        except Exception as e:
            frappe.log_error(
                f"OEV status sync failed for {ref.reference_name}: {e}",
                "office_expense_voucher",
            )
