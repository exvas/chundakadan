import frappe
from frappe.tests.utils import FrappeTestCase


class TestDisplayUnit(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not frappe.db.exists("Display Type", "Cooler"):
            frappe.get_doc({"doctype": "Display Type", "type_name": "Cooler"}).insert()
        if not frappe.db.exists("Supplier", "_Test Display Supplier"):
            frappe.get_doc({"doctype": "Supplier", "supplier_name": "_Test Display Supplier",
                            "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")}).insert()

    def test_new_unit_defaults(self):
        unit = frappe.get_doc({
            "doctype": "Display Unit", "supplier": "_Test Display Supplier",
            "display_type": "Cooler", "description": "Chest cooler",
        }).insert()
        self.assertEqual(unit.current_status, "At Supplier")
        self.assertEqual(unit.current_location_type, "Supplier")
        self.assertEqual(unit.barcode, unit.name)
        self.assertTrue(unit.name.startswith("DISP-"))
