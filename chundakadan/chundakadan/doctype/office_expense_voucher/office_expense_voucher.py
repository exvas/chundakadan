"""Office Expense Voucher

Direct-to-GL expense booking. Posts a 2- or 3-leg GL entry on submit
(Dr Expense, optional Dr Input GST, Cr Expense Payable). Outstanding
amount is cleared by Payment Entries that reference this voucher
(`reference_doctype = "Office Expense Voucher"`).

Mirrors Purchase Invoice's accounting pattern minus item / stock / GST
return complexity — appropriate for utilities, office rent, small
recurring office expenses where a Supplier master is overkill.

Approval workflow piggy-backs on `chundakadan.api.expense_approval`
(see DOCTYPE_CONFIG there). Submit is blocked until the chain is
complete; on final approve, the controller's `on_submit` fires and the
GL entries are written.
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


class OfficeExpenseVoucher(AccountsController):
    """Direct-to-GL expense voucher. See module docstring for shape."""

    # --- Validation / pre-save -----------------------------------------

    def validate(self):
        self._autofill_payable_account()
        self._autofill_party()
        self._autofill_cost_center()
        self._validate_amount()
        self._compute_grand_total()
        # outstanding_amount is set on submit; for drafts, mirror grand_total
        if not self.outstanding_amount or self.docstatus == 0:
            self.outstanding_amount = self.grand_total
        self._set_status_pre_submit()

    def _autofill_party(self):
        """If user didn't pick a Supplier, default to the 'Misc Office
        Expenses' Supplier (auto-created in install hook). Look up by
        supplier_name, not docname — Buying Settings autoname means the
        actual name is something like 'CA-SUPP-00031'.

        Mandatory because ERPNext requires a party on every GL entry
        that hits a Payable-type account.
        """
        if self.party:
            return
        default_docname = frappe.db.get_value(
            "Supplier", {"supplier_name": "Misc Office Expenses"}, "name")
        if default_docname:
            self.party = default_docname

    def _autofill_payable_account(self):
        """If user didn't pick a payable_account, default to the company's
        Expense Payable account."""
        if self.payable_account:
            return
        # Look for an Account named "Expense Payable - <abbr>" first;
        # fall back to any non-group Payable account on the company
        abbr = frappe.get_cached_value("Company", self.company, "abbr") or ""
        guess = f"2210 - Expense Payable - {abbr}"
        if frappe.db.exists("Account", guess):
            self.payable_account = guess
            return
        candidates = frappe.db.sql(
            """
            SELECT name FROM `tabAccount`
            WHERE company = %s
              AND is_group = 0
              AND account_type = 'Payable'
              AND disabled = 0
            ORDER BY (account_name LIKE '%%Expense Payable%%') DESC, lft
            LIMIT 1
            """,
            self.company,
            as_dict=True,
        )
        if candidates:
            self.payable_account = candidates[0]["name"]
        else:
            frappe.throw(_(
                "No Payable account found for {0}. Create '2210 Expense "
                "Payable' under Liabilities or pick one in the Payable "
                "Account field."
            ).format(self.company))

    def _autofill_cost_center(self):
        if self.cost_center:
            return
        cc = frappe.get_cached_value("Company", self.company, "cost_center")
        if not cc:
            cc = frappe.db.get_value(
                "Cost Center",
                {"company": self.company, "is_group": 0, "disabled": 0},
                "name",
            )
        if cc:
            self.cost_center = cc

    def _validate_amount(self):
        if flt(self.amount) <= 0:
            frappe.throw(_("Amount must be greater than zero."))
        if flt(self.tax_amount) < 0:
            frappe.throw(_("Tax Amount cannot be negative."))
        if self.expense_account:
            root_type = frappe.db.get_value(
                "Account", self.expense_account, "root_type")
            if root_type != "Expense":
                frappe.throw(_(
                    "Expense Account {0} must be of root type 'Expense' "
                    "(got '{1}')."
                ).format(self.expense_account, root_type))
        if self.payable_account:
            atype = frappe.db.get_value(
                "Account", self.payable_account, "account_type")
            if atype != "Payable":
                frappe.throw(_(
                    "Payable Account {0} must have Account Type 'Payable' "
                    "(got '{1}')."
                ).format(self.payable_account, atype))

    def _compute_grand_total(self):
        self.grand_total = flt(self.amount) + flt(self.tax_amount)

    def _set_status_pre_submit(self):
        """Status flips during the workflow are managed in two places:
        the approval module sets custom_approval_status, this method
        mirrors that into the user-facing `status` field for drafts."""
        if self.docstatus == 2:
            self.status = "Cancelled"
            return
        if self.docstatus == 0:
            cas = self.custom_approval_status
            if cas == "Rejected":
                self.status = "Rejected"
            elif cas == "Approved":
                self.status = "Approved"  # about to submit
            elif cas == "Partially Approved":
                self.status = "Partially Approved"
            elif cas == "Pending":
                self.status = "Pending Approval"
            else:
                self.status = "Draft"

    # --- Submit / Cancel -----------------------------------------------

    def on_submit(self):
        # Standard AccountsController.on_submit doesn't post GL — that's
        # our job. AccountsController hooks ARE useful for fiscal year
        # checks etc., so call super after our pre-checks.
        self._validate_submit_preconditions()
        self.make_gl_entries()
        self.set_status(update=True)

    def on_cancel(self):
        # Use AccountsController's helper rather than reposting a cancel
        # flag — handles linked Payment Entries properly.
        from erpnext.accounts.utils import unlink_ref_doc_from_payment_entries
        # If any PE references this voucher, allow user to cancel only
        # if PEs are also cancelled. (Standard PI behavior.)
        self.check_no_active_payment_links()
        make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)
        # Also clear payment ledger entries (cascades)
        unlink_ref_doc_from_payment_entries(self)
        self.set_status(update=True)

    def _validate_submit_preconditions(self):
        if not self.expense_account or not self.payable_account:
            frappe.throw(_("Expense Account and Payable Account are required."))
        if not self.cost_center:
            frappe.throw(_("Cost Center is required."))
        if flt(self.grand_total) <= 0:
            frappe.throw(_("Grand Total must be greater than zero."))

    def check_no_active_payment_links(self):
        active = frappe.db.sql(
            """
            SELECT per.parent FROM `tabPayment Entry Reference` per
            JOIN `tabPayment Entry` pe ON pe.name = per.parent
            WHERE per.reference_doctype = %s
              AND per.reference_name = %s
              AND pe.docstatus = 1
            """,
            (self.doctype, self.name),
        )
        if active:
            pe_names = ", ".join(set(p[0] for p in active))
            frappe.throw(_(
                "Cannot cancel — submitted Payment Entries reference this "
                "voucher: {0}. Cancel the Payment Entries first."
            ).format(pe_names))

    # --- GL Entry construction -----------------------------------------

    def make_gl_entries(self, gl_entries=None, from_repost=False):
        """Build the 2- or 3-leg GL entry and post it."""
        gl_entries = gl_entries or self.get_gl_entries()
        if not gl_entries:
            return
        make_gl_entries(
            gl_entries,
            cancel=(self.docstatus == 2),
            update_outstanding="Yes",
            merge_entries=False,
        )

    def get_gl_entries(self) -> list[dict]:
        gl: list[dict] = []
        company_currency = frappe.get_cached_value(
            "Company", self.company, "default_currency")

        # 1. Dr Expense
        gl.append(self.get_gl_dict({
            "account": self.expense_account,
            "against": self.payable_account,
            "debit": flt(self.amount),
            "credit": 0,
            "debit_in_account_currency": flt(self.amount),
            "credit_in_account_currency": 0,
            "cost_center": self.cost_center,
            "against_voucher_type": self.doctype,
            "against_voucher": self.name,
            "remarks": self.description or "",
        }, account_currency=company_currency, item=self))

        # 2. Dr GST input (if claiming + tax > 0)
        if self.claim_gst_input_credit and flt(self.tax_amount) > 0:
            cgst = flt(self.tax_amount) / 2.0
            sgst = flt(self.tax_amount) - cgst
            for acct, amt in (
                (self.gst_account_cgst, cgst),
                (self.gst_account_sgst, sgst),
            ):
                if not acct:
                    continue
                gl.append(self.get_gl_dict({
                    "account": acct,
                    "against": self.payable_account,
                    "debit": amt,
                    "credit": 0,
                    "debit_in_account_currency": amt,
                    "credit_in_account_currency": 0,
                    "cost_center": self.cost_center,
                    "against_voucher_type": self.doctype,
                    "against_voucher": self.name,
                    "remarks": "GST input on " + (self.description or ""),
                }, account_currency=company_currency, item=self))
        elif not self.claim_gst_input_credit and flt(self.tax_amount) > 0:
            # Tax is non-recoverable — fold into the expense leg instead
            # of a separate GL row (cleaner P&L).
            gl[0]["debit"] = flt(gl[0]["debit"]) + flt(self.tax_amount)
            gl[0]["debit_in_account_currency"] = gl[0]["debit"]

        # 3. Cr Payable (always for the full grand_total)
        # Frappe requires party_type + party on GL entries against
        # account_type="Payable" — Supplier supplied from voucher.party.
        gl.append(self.get_gl_dict({
            "account": self.payable_account,
            "against": self.expense_account,
            "debit": 0,
            "credit": flt(self.grand_total),
            "debit_in_account_currency": 0,
            "credit_in_account_currency": flt(self.grand_total),
            "party_type": "Supplier",
            "party": self.party,
            "cost_center": self.cost_center,
            "against_voucher_type": self.doctype,
            "against_voucher": self.name,
            "remarks": self.description or "",
        }, account_currency=company_currency, item=self))

        return gl

    # --- Status --------------------------------------------------------

    def set_status(self, update=False, status=None, update_modified=True):
        """Map outstanding_amount → user-facing status."""
        if self.is_new():
            return
        if not status:
            if self.docstatus == 2:
                status = "Cancelled"
            elif self.docstatus == 0:
                # Draft / approval-pipeline statuses managed in validate
                return
            else:
                outstanding = flt(self.outstanding_amount,
                                  self.precision("outstanding_amount"))
                grand = flt(self.grand_total, self.precision("grand_total"))
                if outstanding <= 0:
                    status = "Paid"
                elif 0 < outstanding < grand:
                    status = "Partly Paid"
                else:
                    status = "Unpaid"
        self.status = status
        if update:
            self.db_set("status", status, update_modified=update_modified)


# --- Module-level utilities (called from hooks / Payment Entry) -----------

@frappe.whitelist()
def make_payment_entry(source_name: str) -> dict:
    """Build a Payment Entry pre-filled to clear this voucher's outstanding.

    ERPNext's standard `get_payment_entry` doesn't know about our custom
    doctype, so we hand-build a minimal PE dict here. Bank account is
    left blank — user picks it on the form.
    """
    source = frappe.get_doc("Office Expense Voucher", source_name)
    if source.docstatus != 1:
        frappe.throw(_("Voucher must be submitted before paying."))
    outstanding = flt(source.outstanding_amount)
    if outstanding <= 0:
        frappe.throw(_("Nothing outstanding on this voucher."))

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Pay"
    pe.posting_date = frappe.utils.nowdate()
    pe.company = source.company
    # Party fields — needed because we're paying down a Payable account
    pe.party_type = "Supplier"
    pe.party = source.party
    pe.party_name = frappe.db.get_value("Supplier", source.party, "supplier_name") \
                    or source.party
    pe.paid_to = source.payable_account
    pe.paid_to_account_currency = frappe.get_cached_value(
        "Account", source.payable_account, "account_currency") or \
        frappe.get_cached_value("Company", source.company, "default_currency")
    pe.paid_amount = outstanding
    pe.received_amount = outstanding
    pe.target_exchange_rate = 1.0
    pe.source_exchange_rate = 1.0
    pe.reference_no = source.reference_no or source.name
    pe.reference_date = source.reference_date or source.posting_date

    pe.append("references", {
        "reference_doctype": source.doctype,
        "reference_name": source.name,
        "due_date": source.posting_date,
        "total_amount": flt(source.grand_total),
        "outstanding_amount": outstanding,
        "allocated_amount": outstanding,
    })
    return pe.as_dict()


def update_voucher_status_on_payment(payment_doc, method=None):
    """`Payment Entry` doc_event hook. When a PE that references an
    Office Expense Voucher is submitted or cancelled, recompute the
    voucher's outstanding_amount + status.

    Frappe's payment_ledger already updates outstanding via
    `update_voucher_outstanding`; we just need to flip status.
    """
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
            voucher.reload()
            voucher.set_status(update=True)
        except Exception as e:
            frappe.log_error(
                f"OEV status sync failed for {ref.reference_name}: {e}",
                "office_expense_voucher",
            )
