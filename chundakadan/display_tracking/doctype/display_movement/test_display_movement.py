import frappe
from frappe.tests.utils import FrappeTestCase


class TestDisplayMovement(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not frappe.db.exists("Display Type", "Rack"):
            frappe.get_doc({"doctype": "Display Type", "type_name": "Rack"}).insert()
        if not frappe.db.exists("Supplier", "_Test Display Supplier"):
            frappe.get_doc({"doctype": "Supplier", "supplier_name": "_Test Display Supplier",
                "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")}).insert()
        if not frappe.db.exists("Customer", "_Test Display Customer"):
            frappe.get_doc({"doctype": "Customer", "customer_name": "_Test Display Customer",
                "customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
                "territory": frappe.db.get_value("Territory", {"is_group": 0}, "name")}).insert()

    def _unit(self):
        return frappe.get_doc({"doctype": "Display Unit", "supplier": "_Test Display Supplier",
                               "display_type": "Rack"}).insert()

    def _move(self, unit, mtype, **kw):
        m = frappe.get_doc({"doctype": "Display Movement", "display_unit": unit.name,
                            "movement_type": mtype, **kw})
        m.insert()
        m.submit()
        return m

    def test_receive_updates_unit(self):
        u = self._unit()
        self._move(u, "Receive at Warehouse", to_location_type="Warehouse")
        u.reload()
        self.assertEqual(u.current_status, "In Warehouse")
        self.assertEqual(u.current_location_type, "Warehouse")

    def test_install_requires_customer(self):
        u = self._unit()
        self._move(u, "Receive at Warehouse", to_location_type="Warehouse")
        with self.assertRaises(frappe.ValidationError):
            self._move(u, "Install at Customer")

    def test_full_install_flow(self):
        u = self._unit()
        self._move(u, "Receive at Warehouse", to_location_type="Warehouse")
        self._move(u, "Install at Customer", customer="_Test Display Customer",
                   expected_return_date="2027-01-01", to_location_type="Customer",
                   to_location="_Test Display Customer")
        u.reload()
        self.assertEqual(u.current_status, "Installed at Customer")
        self.assertEqual(u.current_customer, "_Test Display Customer")
        self.assertEqual(str(u.expected_return_date), "2027-01-01")

    def test_illegal_move_blocked(self):
        u = self._unit()
        with self.assertRaises(frappe.ValidationError):
            self._move(u, "Reserve")

    def test_cancel_recomputes_previous_state(self):
        u = self._unit()
        self._move(u, "Receive at Warehouse", to_location_type="Warehouse")
        m2 = self._move(u, "Reserve")
        u.reload()
        self.assertEqual(u.current_status, "Reserved")
        m2.cancel()
        u.reload()
        self.assertEqual(u.current_status, "In Warehouse")
