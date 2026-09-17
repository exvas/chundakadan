"""Keep Chundakadan's print formats as the default after every migrate.

India Compliance sets Sales Invoice's default print format to "GST Tax
Invoice" whenever it finds none, so on an update the site can fall back to
it. Runs in after_migrate and puts the company format back.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

DEFAULT_PRINT_FORMATS = {
	"Sales Invoice": "Chundakadan GST",
}


def ensure_default_print_formats(*args, **kwargs):
	for doctype, print_format in DEFAULT_PRINT_FORMATS.items():
		if not frappe.db.get_value("Print Format", {"name": print_format, "disabled": 0}):
			# the format lives only in the site DB; never point at a missing one
			continue
		if frappe.get_meta(doctype).default_print_format == print_format:
			continue
		make_property_setter(
			doctype,
			None,
			"default_print_format",
			print_format,
			"Data",
			for_doctype=True,
			validate_fields_for_doctype=False,
			is_system_generated=False,
		)
		frappe.clear_cache(doctype=doctype)
