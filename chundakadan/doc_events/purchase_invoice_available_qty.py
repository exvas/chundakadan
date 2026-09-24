"""An "Avail. Qty" column on the Purchase Invoice items table.

Whoever types a supplier bill wants to see what is already lying in the
warehouse the goods are going into, next to the quantity being received.

The number is the Bin quantity for that row's warehouse — or the invoice's
Set Accepted Warehouse when the row has none. It is refreshed on every
draft save, so a draft always shows current stock; once the invoice is
submitted the figure stays as it was, a record of the stock on hand when
the bill was entered.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import flt

DOCTYPE = "Purchase Invoice Item"
FIELD = "custom_available_qty"

CUSTOM_FIELDS = {
	DOCTYPE: [
		{
			"fieldname": FIELD,
			"label": "Avail. Qty",
			"fieldtype": "Float",
			"insert_after": "qty",
			"read_only": 1,
			"no_copy": 1,
			"print_hide": 1,
			"in_list_view": 1,
			"columns": 1,
			"description": "Stock already in this row's warehouse when the bill was entered.",
		}
	]
}

#: the grid layout lives in purchase_invoice_discount.PROPERTIES, which owns
#: every column width on this table -- including the one Rate gives up for
#: this field. Kept here only so the tests can name the expectation.
GRID_COLUMNS = {"rate": 1, FIELD: 1}


def ensure_purchase_invoice_available_qty(*args, **kwargs):
	"""after_migrate — keep the column on every site."""
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
	# the field has to exist before the discount module can size its column,
	# so re-run that one; it is idempotent
	from chundakadan.doc_events.purchase_invoice_discount import (
		ensure_purchase_invoice_discount_columns,
	)

	ensure_purchase_invoice_discount_columns()
	frappe.clear_cache(doctype="Purchase Invoice")


def warehouse_for(row, parent_warehouse=None):
	return row.get("warehouse") or parent_warehouse


@frappe.whitelist()
def available_qty(item_code: str | None = None, warehouse: str | None = None):
	"""Stock on hand, for the grid to show before the invoice is saved.

	Whitelisted because the people who type supplier bills do not all hold
	Bin read permission, and this exposes one number they are entitled to.
	Both arguments are optional: a half-filled grid row must get a zero,
	not a type error.
	"""
	if not (item_code and warehouse):
		return 0.0
	return flt(
		frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty")
	)


def set_available_qty(doc, method=None):
	"""before_validate — refresh the column while the invoice is a draft."""
	if int(doc.get("docstatus") or 0) != 0:
		return
	parent_warehouse = doc.get("set_warehouse")
	for row in doc.get("items") or []:
		row.set(FIELD, available_qty(row.get("item_code"), warehouse_for(row, parent_warehouse)))
