# Copyright (c) 2026, Chundakadan and contributors
# For license information, please see license.txt
"""Account Ledger Report — a single-account ledger with the narration
front-and-centre. Reads GL Entry, so every voucher type (including the
custom Office Expense Voucher) is included automatically, with its
narration taken from GL Entry.remarks (HTML-stripped defensively).
"""
from html import unescape

import frappe
from frappe import _
from frappe.utils import flt, strip_html


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.get("account"):
        frappe.throw(_("Please select an Account."))
    if not filters.get("company"):
        frappe.throw(_("Please select a Company."))
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
        {"label": _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link",
         "options": "voucher_type", "width": 150},
        {"label": _("Account Name"), "fieldname": "against_account", "fieldtype": "Data", "width": 200},
        {"label": _("Narration"), "fieldname": "narration", "fieldtype": "Data", "width": 420},
        {"label": _("Debit Amount"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": _("Credit Amount"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": _("Closing Balance"), "fieldname": "balance", "fieldtype": "Data", "width": 140},
    ]


def _fmt(bal):
    return "{:,.2f}  {}".format(abs(flt(bal)), "Dr" if flt(bal) >= 0 else "Cr")


def get_data(filters):
    cond = "gle.account = %(account)s AND gle.company = %(company)s AND gle.is_cancelled = 0"
    params = {
        "account": filters.account, "company": filters.company,
        "from_date": filters.get("from_date"), "to_date": filters.get("to_date"),
    }

    # Opening balance = net of everything before from_date
    opening = 0.0
    if filters.get("from_date"):
        row = frappe.db.sql(
            f"SELECT SUM(gle.debit - gle.credit) AS bal FROM `tabGL Entry` gle "
            f"WHERE {cond} AND gle.posting_date < %(from_date)s", params, as_dict=True)
        opening = flt(row[0].bal) if row and row[0].bal is not None else 0.0

    date_clause = ""
    if filters.get("from_date"):
        date_clause += " AND gle.posting_date >= %(from_date)s"
    if filters.get("to_date"):
        date_clause += " AND gle.posting_date <= %(to_date)s"

    entries = frappe.db.sql(
        f"""SELECT gle.posting_date, gle.voucher_type, gle.voucher_no,
                   gle.against AS against_account, gle.remarks,
                   gle.debit, gle.credit
            FROM `tabGL Entry` gle
            WHERE {cond} {date_clause}
            ORDER BY gle.posting_date, gle.creation""",
        params, as_dict=True)

    data = [{
        "posting_date": filters.get("from_date"),
        "narration": _("Opening Balance"),
        "balance": _fmt(opening),
    }]

    balance = opening
    total_debit = total_credit = 0.0
    for e in entries:
        balance += flt(e.debit) - flt(e.credit)
        total_debit += flt(e.debit)
        total_credit += flt(e.credit)
        data.append({
            "posting_date": e.posting_date,
            "voucher_type": e.voucher_type,
            "voucher_no": e.voucher_no,
            "against_account": e.against_account,
            "narration": unescape(strip_html(e.remarks or "")).strip(),
            "debit": flt(e.debit),
            "credit": flt(e.credit),
            "balance": _fmt(balance),
        })

    data.append({
        "narration": _("Closing Balance"),
        "debit": total_debit,
        "credit": total_credit,
        "balance": _fmt(balance),
    })
    return data
