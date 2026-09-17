"""Item-level discount columns on the Purchase Invoice items table.

Supplier bills list a List Price and a Discount % per line. ERPNext already
calculates both ways (buying.js / taxes_and_totals.js):
  Discount %      -> Discount Amount and Rate
  Discount Amount -> Discount % and Rate
Both are per unit and work from Price List Rate. The fields are simply not
in the grid, and the discount fields stay hidden until a price list rate is
set, so this shows them as columns. Runs in after_migrate.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

DOCTYPE = "Purchase Invoice Item"

# fieldname -> {property: (value, property_type)}
# Grid columns add up to 10 (Frappe's grid width).
PROPERTIES = {
	"item_code": {"columns": (2, "Int")},
	"qty": {"columns": (1, "Int")},
	"price_list_rate": {"in_list_view": (1, "Check"), "columns": (1, "Int"), "label": ("List Price", "Data")},
	"discount_percentage": {"in_list_view": (1, "Check"), "columns": (1, "Int"), "depends_on": ("", "Data"), "label": ("Disc %", "Data")},
	"discount_amount": {"in_list_view": (1, "Check"), "columns": (1, "Int"), "depends_on": ("", "Data"), "label": ("Disc Amnt", "Data")},
	"rate": {"columns": (2, "Int")},
	"amount": {"columns": (2, "Int")},
}


# Per-piece prices such as 0.85 less 57% need more than the 2 decimals INR
# gives: a rate of 0.3655 rounded to 0.37 turns 48,000 pcs from 17,544 into
# 17,760. Only the rate fields get 4 decimals; amounts and totals stay at 2.
RATE_PRECISION = "4"
RATE_FIELDS = (
	"price_list_rate",
	"base_price_list_rate",
	"rate_with_margin",
	"base_rate_with_margin",
	"discount_amount",
	"rate",
	"base_rate",
	"net_rate",
	"base_net_rate",
	"stock_uom_rate",
)


def ensure_purchase_invoice_discount_columns(*args, **kwargs):
	meta = frappe.get_meta(DOCTYPE)
	for fieldname, properties in PROPERTIES.items():
		if not meta.get_field(fieldname):
			continue
		for prop, (value, prop_type) in properties.items():
			make_property_setter(DOCTYPE, fieldname, prop, value, prop_type, validate_fields_for_doctype=False)
	for fieldname in RATE_FIELDS:
		if meta.get_field(fieldname):
			make_property_setter(DOCTYPE, fieldname, "precision", RATE_PRECISION, "Select", validate_fields_for_doctype=False)
	frappe.clear_cache(doctype="Purchase Invoice")
