"""Update Stock on invoices is controlled from Chundakadan Settings.

Nobody may tick or untick the field on the form: it is read-only and the
server writes the value from the setting on every save.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import cint

SETTINGS = "Chundakadan Settings"

# doctype -> (settings fieldname, label, default when the setting was never saved)
UPDATE_STOCK_SETTINGS = {
	"Sales Invoice": ("si_update_stock", "Sales Invoice: Update Stock", 0),
	"Purchase Invoice": ("pi_update_stock", "Purchase Invoice: Update Stock", 1),
}


def get_update_stock(doctype: str) -> int:
	fieldname, _label, default = UPDATE_STOCK_SETTINGS[doctype]
	value = frappe.db.get_single_value(SETTINGS, fieldname)
	return default if value is None else cint(value)


def ensure_update_stock_settings(*args, **kwargs):
	"""after_migrate: create the toggles and lock the field on both doctypes."""
	if not frappe.db.exists("DocType", SETTINGS):
		return

	fields = []
	previous = "enforce_b2b_gstin_billing"
	for doctype, (fieldname, label, default) in UPDATE_STOCK_SETTINGS.items():
		fields.append(
			{
				"fieldname": fieldname,
				"label": label,
				"fieldtype": "Check",
				"default": str(default),
				"insert_after": previous,
				"description": f"Controls Update Stock on every {doctype}. The field is read-only on the form.",
				"module": "Chundakadan",
			}
		)
		previous = fieldname
	create_custom_fields({SETTINGS: fields}, update=True)

	for doctype, (fieldname, _label, default) in UPDATE_STOCK_SETTINGS.items():
		if frappe.db.get_single_value(SETTINGS, fieldname) is None:
			frappe.db.set_single_value(SETTINGS, fieldname, default)
		make_property_setter(
			doctype, "update_stock", "read_only", 1, "Check", validate_fields_for_doctype=False
		)
		frappe.clear_cache(doctype=doctype)

	frappe.db.commit()
