import unittest
import frappe
from chundakadan.display_tracking.transitions import (
    resolve_transition, TRANSITIONS, LOCATION_DOCTYPE,
)


class TestTransitions(unittest.TestCase):
    def test_receive_from_at_supplier(self):
        t = resolve_transition("Receive at Warehouse", "At Supplier")
        self.assertEqual(t["to_status"], "In Warehouse")
        self.assertEqual(t["to_location_type"], "Warehouse")

    def test_install_sets_installed(self):
        t = resolve_transition("Install at Customer", "In Warehouse")
        self.assertEqual(t["to_status"], "Installed at Customer")
        self.assertIn("customer", t["requires"])
        self.assertIn("expected_return_date", t["requires"])

    def test_return_to_warehouse_sets_returned(self):
        t = resolve_transition("Return to Warehouse", "Installed at Customer")
        self.assertEqual(t["to_status"], "Returned")

    def test_dispatch_leaves_location_unchanged(self):
        t = resolve_transition("Dispatch", "In Warehouse")
        self.assertEqual(t["to_status"], "In Transit")
        self.assertIsNone(t["to_location_type"])

    def test_illegal_transition_raises(self):
        with self.assertRaises(frappe.ValidationError):
            resolve_transition("Reserve", "Installed at Customer")

    def test_mark_damaged_allowed_from_any(self):
        for st in ["In Warehouse", "Installed at Customer", "In Transit"]:
            t = resolve_transition("Mark Damaged", st)
            self.assertEqual(t["to_status"], "Damaged")

    def test_location_doctype_map(self):
        self.assertEqual(LOCATION_DOCTYPE["Warehouse"], "Warehouse Rack")
        self.assertEqual(LOCATION_DOCTYPE["Dealer"], "Customer")
        self.assertEqual(LOCATION_DOCTYPE["Service Center"], "Display Service Center")
