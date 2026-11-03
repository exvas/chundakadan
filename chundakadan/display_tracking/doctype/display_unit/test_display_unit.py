import frappe
from frappe.tests.utils import FrappeTestCase

SUPPLIER = "_Test Display Supplier"


class TestDisplayUnit(FrappeTestCase):
	def setUp(self):
		"""Per test, not per class: FrappeTestCase rolls back after each test.
		Supplier follows a naming series, so keep the name insert() gives back
		rather than the one we typed."""
		if not frappe.db.exists("Display Type", "Cooler"):
			frappe.get_doc({"doctype": "Display Type", "type_name": "Cooler"}).insert()

		self.supplier = frappe.db.get_value("Supplier", {"supplier_name": SUPPLIER}, "name")
		if not self.supplier:
			self.supplier = (
				frappe.get_doc(
					{
						"doctype": "Supplier",
						"supplier_name": SUPPLIER,
						"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
					}
				)
				.insert()
				.name
			)

	def test_new_unit_defaults(self):
		unit = frappe.get_doc(
			{
				"doctype": "Display Unit",
				"supplier": self.supplier,
				"display_type": "Cooler",
				"description": "Chest cooler",
			}
		).insert()
		self.assertEqual(unit.current_status, "At Supplier")
		self.assertEqual(unit.current_location_type, "Supplier")
		self.assertEqual(unit.barcode, unit.name)
		self.assertTrue(unit.name.startswith("DISP-"))
