import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.patches import hide_invoice_fields as patch

test_ignore = ["Sales Invoice", "Purchase Invoice"]


class TestHideInvoiceFields(FrappeTestCase):
	def test_reapplies_after_a_reset(self):
		# what saving Stock Settings with show_barcode_field on does
		for dt in ("Sales Invoice", "Purchase Invoice"):
			frappe.make_property_setter(
				{"doctype": dt, "fieldname": "scan_barcode", "property": "hidden", "value": 0},
				validate_fields_for_doctype=False,
			)
			frappe.clear_cache(doctype=dt)
			self.assertFalse(frappe.get_meta(dt, cached=False).get_field("scan_barcode").hidden)

		patch.execute()

		for dt in ("Sales Invoice", "Purchase Invoice"):
			self.assertTrue(frappe.get_meta(dt, cached=False).get_field("scan_barcode").hidden, dt)
