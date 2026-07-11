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
        # tax_amount on each line is treated as a non-recoverable add-on
        # (folded into the same expense account in the GL). For real GST
        # input credit, book via Purchase Invoice instead.
        subtotal = sum(flt(r.amount) for r in (self.items or []))
        line_taxes = sum(flt(r.get("tax_amount") or 0)
                          for r in (self.items or []))
        self.subtotal = subtotal
        self.grand_total = subtotal + line_taxes

    def _validate_payment_target(self):
        """Payment-target invariant — driven by the 'Pay Later' flag:

          - Pay Later UNCHECKED (default, immediate payment):
              paid_from is mandatory. If payable_account is ALSO set,
              GL passes through it (4-leg audit). If not, direct 2-leg.

          - Pay Later CHECKED (deferred):
              paid_from is IGNORED (cleared at validate). Voucher books
              Dr Expense / Cr Payable; user runs 'Make Payment' later
              to settle.
        """
        if self.pay_later:
            # Ignore + clear any stray paid_from value
            self.paid_from = None
            if not self.payable_account:
                frappe.throw(_(
                    "Payable Account is required when 'Pay Later' is "
                    "ticked. Set a default in Chundakadan Settings to "
                    "auto-fill it."))
        else:
            if not self.paid_from:
                frappe.throw(_(
                    "<b>Paid From</b> (Bank / Cash) is required. Tick "
                    "'Pay Later' if you want to defer the payment."))

    def _set_status_pre_submit(self):
        # Document Status (status field) is PAYMENT-only — workflow state
        # lives in custom_approval_status. Pre-submit, the doc isn't
        # paid yet, so status stays Draft until docstatus=1.
        if self.docstatus == 2:
            self.status = "Cancelled"
        elif self.docstatus == 0:
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

    def _narration(self, line_desc=None):
        """Clean, HTML-stripped narration for GL `remarks` so a single-account
        ledger reads well on ANY leg (bank / payable / expense).

        Priority: the line's description → the voucher description → a
        constructed "Paid to <vendor> for <first line>" fallback.
        The description fields are rich-text (Text Editor), so strip HTML.
        """
        from frappe.utils import strip_html
        from html import unescape
        text = (unescape(strip_html(line_desc or "")).strip()
                or unescape(strip_html(self.description or "")).strip())
        if not text:
            first_item = (unescape(strip_html(self.items[0].description or "")).strip()
                          if self.items else "")
            vendor = (self.vendor_payee or "").strip()
            if vendor and first_item:
                text = f"Paid to {vendor} for {first_item}"
            elif vendor:
                text = f"Paid to {vendor}"
            else:
                text = first_item
        return text

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

        # 1. Debits — one row per expense line (line tax_amount, if any,
        # folded into the expense account; OEV treats it as
        # non-recoverable. Use Purchase Invoice for proper GST input credit.)
        for row in (self.items or []):
            cc = row.cost_center or self._fallback_cost_center()
            line_dr = flt(row.amount) + flt(row.get("tax_amount") or 0)
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
                "remarks": self._narration(row.description),
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
                "remarks": self._narration(),
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
                "remarks": self._narration(),
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
                "remarks": self._narration(),
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
                "remarks": self._narration(),
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
        """Compute the PAYMENT lifecycle status + paid/balance fields.

        Post-submit:
          - paid_from-mode (immediate payment) → Paid, balance=0, paid=grand_total
          - pay_later mode → Unpaid / Partially Paid / Paid based on JV
            settlements; paid/balance computed accordingly
        """
        if self.is_new():
            return
        grand = flt(self.grand_total, self.precision("grand_total"))
        if not status:
            if self.docstatus == 2:
                status = "Cancelled"
                paid = balance = 0.0
            elif self.docstatus == 0:
                return  # stays "Draft" — pre-submit
            else:
                if self.paid_from:
                    # Immediate payment — fully paid on OEV submit
                    status = "Paid"
                    paid = grand
                    balance = 0.0
                else:
                    settled = self._payable_settled_amount()
                    paid = settled
                    balance = max(0.0, grand - settled)
                    if settled <= 0:
                        status = "Unpaid"
                    elif settled < grand:
                        status = "Partially Paid"
                    else:
                        status = "Paid"
        else:
            paid = flt(self.paid_amount)
            balance = flt(self.balance_amount)

        self.status = status
        self.paid_amount = paid
        self.balance_amount = balance
        if update:
            self.db_set({
                "status": status,
                "paid_amount": paid,
                "balance_amount": balance,
            }, update_modified=update_modified)

    def _payable_settled_amount(self) -> float:
        """Sum of Dr Payable amounts on active GL Entries that reference
        this voucher BUT come from a different voucher (i.e. JV/PE
        clearing entries). Used to detect partial vs full settlement."""
        rows = frappe.db.sql(
            """
            SELECT COALESCE(SUM(debit), 0) AS d
            FROM `tabGL Entry`
            WHERE against_voucher_type = %(vt)s
              AND against_voucher = %(vn)s
              AND voucher_no != %(vn)s
              AND account = %(payable)s
              AND is_cancelled = 0
            """,
            {"vt": self.doctype, "vn": self.name,
             "payable": self.payable_account},
            as_dict=True,
        )
        return flt(rows[0]["d"]) if rows else 0.0
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
    """Build a Journal Entry (NOT a Payment Entry) to clear the Payable
    Account for a deferred-mode voucher (pay_later=1).

    Why JV instead of PE: our Expense Payable account is account_type=''
    (deliberately, to keep these out of the AR/AP report). ERPNext's PE
    enforces a Supplier party on any 'Pay' to a Payable account — we
    don't have a supplier here. A JV is happy with any liability
    account + no party.

    Returns a JV dict the form syncs into a new draft. User picks the
    Bank/Cash account on line 2 then submits.
    """
    source = frappe.get_doc("Office Expense Voucher", source_name)
    if source.docstatus != 1:
        frappe.throw(_("Voucher must be submitted before paying."))
    if source.paid_from:
        frappe.throw(_(
            "This voucher was already paid via {0}. "
            "No further payment needed.").format(source.paid_from))
    if not source.payable_account:
        frappe.throw(_(
            "No Payable Account set — voucher posting state is invalid."))

    # Pay only the OUTSTANDING balance — supports partial-settlement chains.
    # If balance_amount is stale (not computed yet), fall back to grand_total.
    source.set_status(update=False)  # refresh in-memory paid/balance
    amount = flt(source.balance_amount) or flt(source.grand_total)
    if amount <= 0:
        frappe.throw(_("Nothing left to pay on this voucher."))
    cc = (source.items[0].cost_center if source.items else None) or \
         frappe.get_cached_value("Company", source.company, "cost_center")

    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Bank Entry"
    je.posting_date = frappe.utils.nowdate()
    je.company = source.company
    je.cheque_no = source.reference_no or source.name
    je.cheque_date = source.reference_date or source.posting_date
    je.user_remark = (
        f"Settling Office Expense Voucher {source.name} (₹{amount:,.2f}) — "
        f"{source.vendor_payee or source.description or ''}"
    )
    # Leg 1: Dr Payable Account (clears the liability)
    je.append("accounts", {
        "account": source.payable_account,
        "debit_in_account_currency": amount,
        "credit_in_account_currency": 0,
        "cost_center": cc,
        "reference_type": source.doctype,
        "reference_name": source.name,
        "user_remark": f"Settle {source.name}",
    })
    # Leg 2: Cr Bank/Cash — user fills the account on the form
    je.append("accounts", {
        "debit_in_account_currency": 0,
        "credit_in_account_currency": amount,
        "cost_center": cc,
    })
    return je.as_dict()


def update_voucher_status_on_payment(payment_doc, method=None):
    """Hook for Journal Entry (formerly Payment Entry).

    When a JV with an account-row referencing an OEV is submitted /
    cancelled, flip the voucher's status: Paid on submit, back to
    Unpaid on cancel. Idempotent — only acts on deferred-mode
    vouchers (paid_from blank, payable_account set)."""
    refs = set()
    # Journal Entry's account rows expose reference_type / reference_name
    for row in (payment_doc.get("accounts") or []):
        if row.get("reference_type") == "Office Expense Voucher" \
                and row.get("reference_name"):
            refs.add(row.reference_name)
    # Payment Entry's references table — kept for legacy / safety
    for row in (payment_doc.get("references") or []):
        if row.get("reference_doctype") == "Office Expense Voucher" \
                and row.get("reference_name"):
            refs.add(row.reference_name)
    if not refs:
        return
    for name in refs:
        try:
            voucher = frappe.get_doc("Office Expense Voucher", name)
            if voucher.docstatus != 1:
                continue
            if voucher.paid_from:
                # Immediate-payment mode — already 'Paid' on OEV submit
                continue
            # Recompute status from CURRENT GL state — handles partial
            # payments naturally (multiple JVs settling fractions of
            # the voucher's outstanding amount).
            voucher.set_status(update=True)
        except Exception as e:
            frappe.log_error(
                f"OEV status sync failed for {name}: {e}",
                "office_expense_voucher",
            )
