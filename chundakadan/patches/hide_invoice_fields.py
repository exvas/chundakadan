import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

# Fields the business asked to hide on invoices. Kept in code so every site
# (incl. Frappe Cloud after migration) gets them on `bench migrate`.
HIDDEN_FIELDS = {
	"Sales Invoice": [
		"scan_barcode",
		"shipping_rule",
		"incoterm",
		"named_place",
		"project",
		"time_sheet_list",
		"loyalty_points_redemption",
	],
	"Purchase Invoice": [
		"scan_barcode",
		"shipping_rule",
		"incoterm",
		"named_place",
		"project",
		"is_subcontracted",
		"rejected_warehouse",
		"raw_materials_supplied",
		"supplied_items",
	],
	"Purchase Invoice Item": [
		"rejected_warehouse",
	],
}


def execute():
	for doctype, fields in HIDDEN_FIELDS.items():
		meta = frappe.get_meta(doctype)
		for fieldname in fields:
			if not meta.get_field(fieldname):
				continue
			make_property_setter(
				doctype, fieldname, "hidden", 1, "Check", validate_fields_for_doctype=False
			)
		frappe.clear_cache(doctype=doctype)
