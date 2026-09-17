import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events.print_format_defaults import DEFAULT_PRINT_FORMATS, ensure_default_print_formats


class TestDefaultPrintFormats(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()
		frappe.clear_cache(doctype="Sales Invoice")

	def _require_format(self):
		# the real format is a site-only record; make one inside the test transaction
		if not frappe.db.exists("Print Format", DEFAULT_PRINT_FORMATS["Sales Invoice"]):
			frappe.get_doc({"doctype": "Print Format", "name": "Chundakadan GST", "doc_type": "Sales Invoice", "module": "Chundakadan", "standard": "No", "print_format_type": "Jinja", "html": "<div></div>", "custom_format": 1}).insert()

	def test_restores_after_india_compliance_default(self):
		self._require_format()
		make_property_setter("Sales Invoice", None, "default_print_format", "GST Tax Invoice", "Data", for_doctype=True, validate_fields_for_doctype=False)
		frappe.clear_cache(doctype="Sales Invoice")
		self.assertEqual(frappe.get_meta("Sales Invoice").default_print_format, "GST Tax Invoice")
		ensure_default_print_formats()
		self.assertEqual(frappe.get_meta("Sales Invoice").default_print_format, "Chundakadan GST")
		setters = frappe.get_all("Property Setter", filters={"doc_type": "Sales Invoice", "property": "default_print_format"})
		self.assertEqual(len(setters), 1)

	def test_idempotent(self):
		self._require_format()
		ensure_default_print_formats()
		ensure_default_print_formats()
		self.assertEqual(frappe.get_meta("Sales Invoice").default_print_format, "Chundakadan GST")

	def test_skips_disabled_format(self):
		self._require_format()
		make_property_setter("Sales Invoice", None, "default_print_format", "GST Tax Invoice", "Data", for_doctype=True, validate_fields_for_doctype=False)
		frappe.db.set_value("Print Format", "Chundakadan GST", "disabled", 1)
		frappe.clear_cache(doctype="Sales Invoice")
		ensure_default_print_formats()
		self.assertEqual(frappe.get_meta("Sales Invoice").default_print_format, "GST Tax Invoice")
