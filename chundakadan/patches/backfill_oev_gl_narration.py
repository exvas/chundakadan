"""Backfill GL Entry.remarks for existing Office Expense Vouchers so the
account ledger shows the real narration (the line description) instead of a
bare vendor name / raw HTML. remarks is not ledger-load-bearing, so a direct
db.set_value is safe.
"""
from html import unescape

import frappe
from frappe.utils import strip_html


def _clean(s):
    return unescape(strip_html(s or "")).strip()


def execute():
    names = frappe.get_all("Office Expense Voucher", filters={"docstatus": 1}, pluck="name")
    updated = 0
    for name in names:
        doc = frappe.get_doc("Office Expense Voucher", name)
        acct_desc = {}          # expense_account -> [line descriptions]
        all_descs = []
        for r in doc.items:
            d = _clean(r.description)
            if d:
                all_descs.append(d)
                acct_desc.setdefault(r.expense_account, []).append(d)
        # Narration for the non-expense (bank / payable) legs.
        voucher_narr = (_clean(doc.description) or "; ".join(all_descs)
                        or ("Paid to {0}".format((doc.vendor_payee or "").strip())
                            if (doc.vendor_payee or "").strip() else ""))
        gles = frappe.get_all(
            "GL Entry",
            filters={"voucher_type": "Office Expense Voucher", "voucher_no": name, "is_cancelled": 0},
            fields=["name", "account"])
        for g in gles:
            new = "; ".join(acct_desc[g.account]) if g.account in acct_desc else voucher_narr
            if new:
                frappe.db.set_value("GL Entry", g.name, "remarks", new, update_modified=False)
                updated += 1
    frappe.db.commit()
    print("backfill_oev_gl_narration: updated {0} GL entries across {1} OEVs".format(updated, len(names)))
