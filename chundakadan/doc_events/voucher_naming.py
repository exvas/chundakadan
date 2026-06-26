# Company-aware transaction numbering for cash / bank / journal vouchers.
#
# Confirmed with client (Rashid Chundakadan, 2026-06-26):
#   {CODE}-{COMPANY_ABBR}-{YY}-{####}   e.g. CP-CA-26-0001
#
#   CODE : CP cash payment | BP bank payment | CR cash receipt |
#          BR bank receipt   (all Payment Entry)
#          JV journal        | CON contra        (Journal Entry)
#   YY   : 2-digit year taken from the voucher's posting_date
#   #### : 4-digit running counter, resets per (code, company, year)
#
# Two companies (Chundakadan Agencies = CA, Chundakadan Home Stop = CHS)
# each get an INDEPENDENT counter because the company abbr is part of the
# name. Frappe document names are unique per doctype, so two companies
# cannot share an identical number — the abbr is what keeps them separate.
#
# Wired as doc_events "autoname" hooks for Payment Entry + Journal Entry.
# The autoname hook runs before Frappe's naming_series: fallback
# (frappe/model/naming.set_new_name), so setting doc.name here wins.

import frappe
from frappe.model.naming import make_autoname
from frappe.utils import getdate


def _company_abbr(company):
    """Company.abbr (CA / CHS), upper-cased. Defensive fallback to a slug
    of the company name so naming never crashes on a missing abbr."""
    if not company:
        return "NA"
    abbr = frappe.get_cached_value("Company", company, "abbr")
    return (abbr or company).strip()[:6].upper()


def _yy(date_value):
    """2-digit year from the posting date (so backdated vouchers carry the
    correct year). getdate(None) falls back to today."""
    return getdate(date_value).strftime("%y")


def _is_cash(mode_of_payment, account=None):
    """True => Cash voucher, False => Bank voucher.

    Resolve from Mode of Payment.type first (Cash vs Bank — handles many
    distinct bank modes like Cheque / Wire Transfer). If the mode is blank,
    fall back to the bank/cash account's account_type. Default Bank."""
    if mode_of_payment:
        t = frappe.get_cached_value("Mode of Payment", mode_of_payment, "type")
        if t == "Cash":
            return True
        if t == "Bank":
            return False
    if account:
        if frappe.get_cached_value("Account", account, "account_type") == "Cash":
            return True
    return False


def _apply(doc, code):
    abbr = _company_abbr(doc.get("company"))
    yy = _yy(doc.get("posting_date"))
    doc.name = make_autoname(f"{code}-{abbr}-{yy}-.####", doc=doc)


def payment_entry_autoname(doc, method=None):
    ptype = doc.get("payment_type")
    if ptype == "Pay":
        code = "CP" if _is_cash(doc.get("mode_of_payment"), doc.get("paid_from")) else "BP"
    elif ptype == "Receive":
        code = "CR" if _is_cash(doc.get("mode_of_payment"), doc.get("paid_to")) else "BR"
    else:
        # Internal Transfer (money moved between own cash/bank accounts) —
        # treat as a contra movement.
        code = "CON"
    _apply(doc, code)


def journal_entry_autoname(doc, method=None):
    # Contra Entry => CON; every other journal subtype (Journal Entry,
    # Bank Entry, Cash Entry, Opening Entry, ...) => JV.
    code = "CON" if doc.get("voucher_type") == "Contra Entry" else "JV"
    _apply(doc, code)
