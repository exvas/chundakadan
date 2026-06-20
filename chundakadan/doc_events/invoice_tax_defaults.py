# Copyright (c) 2026, Ashkar and contributors
# Wired from chundakadan/hooks.py as before_insert hooks on
# Sales Invoice + Purchase Invoice.

"""Auto-apply chundakadan In-State GST defaults to new invoices.

Chundakadan is a Kerala-only intra-state business — 95% of sales/purchases
are In-State GST 18%. Without these defaults, every new invoice needs HR
to remember to fill the tax fields, which they routinely forget. Without
tax_category + taxes_and_charges, india_compliance can't compute GST and
the invoice's grand_total = net_total (wrong number on the print).

Behaviour:
  • Sales Invoice (new + blank tax fields):
      - tax_category = "In-State"
      - taxes_and_charges = "Output GST In-state - CA"
  • Purchase Invoice (new + blank tax fields):
      - tax_category = "In-State"
      - taxes_and_charges = "Input GST In-state - CA"

Never override an explicit value the user already typed — so an
Out-State invoice manually set up by HR survives the hook.

This sets the HEADER fields only; the tax row population from template
happens in Frappe's standard validate() via set_taxes() when the template
field is set on a doc with no rows.
"""

import frappe

_TAX_CATEGORY      = "In-State"
_SALES_TEMPLATE    = "Output GST In-state - CA"
_PURCHASE_TEMPLATE = "Input GST In-state - CA"


def apply_sales_invoice_defaults(doc, method=None):
    """before_insert on Sales Invoice."""
    if not doc.get("tax_category"):
        if frappe.db.exists("Tax Category", _TAX_CATEGORY):
            doc.tax_category = _TAX_CATEGORY
    if not doc.get("taxes_and_charges"):
        if frappe.db.exists("Sales Taxes and Charges Template", _SALES_TEMPLATE):
            doc.taxes_and_charges = _SALES_TEMPLATE


def apply_purchase_invoice_defaults(doc, method=None):
    """before_insert on Purchase Invoice."""
    if not doc.get("tax_category"):
        if frappe.db.exists("Tax Category", _TAX_CATEGORY):
            doc.tax_category = _TAX_CATEGORY
    if not doc.get("taxes_and_charges"):
        if frappe.db.exists("Purchase Taxes and Charges Template", _PURCHASE_TEMPLATE):
            doc.taxes_and_charges = _PURCHASE_TEMPLATE
