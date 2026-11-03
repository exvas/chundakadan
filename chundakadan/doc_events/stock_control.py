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
	"""The setting, or the default where nobody has ever saved one.

	Read the Singles row rather than frappe.db.get_single_value: that casts
	through the fieldtype, and cast_fieldtype("Check", None) is 0, so a
	setting that was never saved was indistinguishable from one deliberately
	turned off and the default could never apply — Purchase Invoice's
	documented default of 1 silently read as 0.
	"""
	fieldname, _label, default = UPDATE_STOCK_SETTINGS[doctype]
	# order_by=None: the Singles table has no `modified` column to sort by
	saved = frappe.db.get_value("Singles", {"doctype": SETTINGS, "field": fieldname}, "value", order_by=None)
	return default if saved is None else cint(saved)


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
	# Seed the default only for a toggle that does not exist yet: once the
	# field is there its stored value is the business decision, and a Check
	# reads back as 0 rather than None, so "is None" would never seed it.
	new_fields = {
		fieldname
		for _doctype, (fieldname, _label, _default) in UPDATE_STOCK_SETTINGS.items()
		if not frappe.db.exists("Custom Field", f"{SETTINGS}-{fieldname}")
	}

	create_custom_fields({SETTINGS: fields}, update=True)

	for doctype, (fieldname, _label, default) in UPDATE_STOCK_SETTINGS.items():
		if fieldname in new_fields:
			frappe.db.set_single_value(SETTINGS, fieldname, default)
		make_property_setter(
			doctype, "update_stock", "read_only", 1, "Check", validate_fields_for_doctype=False
		)
		frappe.clear_cache(doctype=doctype)

	frappe.db.commit()
