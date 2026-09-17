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
	"discount_percentage": {"in_list_view": (1, "Check"), "columns": (1, "Int"), "depends_on": ("", "Data"), "label": ("Discount %", "Data")},
	"discount_amount": {"in_list_view": (1, "Check"), "columns": (1, "Int"), "depends_on": ("", "Data"), "label": ("Discount Amount", "Data")},
	"rate": {"columns": (2, "Int")},
	"amount": {"columns": (2, "Int")},
}


def ensure_purchase_invoice_discount_columns(*args, **kwargs):
	meta = frappe.get_meta(DOCTYPE)
	for fieldname, properties in PROPERTIES.items():
		if not meta.get_field(fieldname):
			continue
		for prop, (value, prop_type) in properties.items():
			make_property_setter(DOCTYPE, fieldname, prop, value, prop_type, validate_fields_for_doctype=False)
	frappe.clear_cache(doctype="Purchase Invoice")
