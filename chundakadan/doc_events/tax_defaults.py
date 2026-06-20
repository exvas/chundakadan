# Copyright (c) 2026, Ashkar and contributors
# Wired from chundakadan/hooks.py as before_insert hooks on Item + Customer.

"""Auto-apply chundakadan tax defaults to NEW Items + Customers.

Chundakadan is a single-state Kerala business — all sales are intra-state
(In-State) GST and 18% is the most common rate. Without these defaults
every new master needs HR to remember to fill the tax fields, which
they routinely forget. Then PI/SI calculations miss tax and HR has to
go back and re-edit.

Behaviour:
  • Item:
      - custom_tax_template = "Tax"            (if blank)
      - taxes child row     = GST 18% - CA / In-State   (if no row exists)
  • Customer:
      - tax_category = "In-State"               (if blank)

NEVER OVERRIDE an explicit value the user already typed. So bulk imports
that set custom_tax_template to "Tax Free" or tax_category to "Out-State"
still survive.
"""

import frappe

_TAX_TEMPLATE = "Tax"
_ITEM_TAX_TEMPLATE = "GST 18% - CA"
_TAX_CATEGORY = "In-State"


def apply_item_defaults(doc, method=None):
    """before_insert on Item."""
    # 1. Top-level Tax Template link
    if not doc.get("custom_tax_template"):
        if frappe.db.exists("Tax Template", _TAX_TEMPLATE):
            doc.custom_tax_template = _TAX_TEMPLATE

    # 2. Item Tax child row — only add if no row exists at all (don't
    # second-guess a user who deliberately set up multi-rate taxes).
    if not doc.get("taxes") and frappe.db.exists("Item Tax Template", _ITEM_TAX_TEMPLATE):
        doc.append("taxes", {
            "item_tax_template": _ITEM_TAX_TEMPLATE,
            "tax_category": _TAX_CATEGORY if frappe.db.exists("Tax Category", _TAX_CATEGORY) else None,
            "minimum_net_rate": 0,
            "maximum_net_rate": 0,
        })


def apply_customer_defaults(doc, method=None):
    """before_insert on Customer."""
    if not doc.get("tax_category"):
        if frappe.db.exists("Tax Category", _TAX_CATEGORY):
            doc.tax_category = _TAX_CATEGORY
