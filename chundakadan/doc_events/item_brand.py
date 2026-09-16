"""Brand is mandatory on Item.

Kept as an after_migrate hook so it survives app updates and is present on
any site running the app. Every item was given a brand before this was
switched on (2026-09-16), so existing items keep saving.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def ensure_item_brand_mandatory(*args, **kwargs):
	if not frappe.get_meta("Item").get_field("brand"):
		return
	make_property_setter("Item", "brand", "reqd", 1, "Check", validate_fields_for_doctype=False)
	frappe.clear_cache(doctype="Item")
	frappe.db.commit()
