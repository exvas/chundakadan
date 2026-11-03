import frappe
from frappe.tests.utils import FrappeTestCase

SUPPLIER = "_Test Display Supplier"
CUSTOMER = "_Test Display Customer"
RACK = "_Test Display Rack"


class TestDisplayMovement(FrappeTestCase):
	def setUp(self):
		"""Per test, not per class: FrappeTestCase rolls back after each test,
		so anything setUpClass inserts is gone by the second one — which is why
		every test but the first died with "Could not find Supplier".

		Supplier and Customer follow a naming series, so their docname is not
		the name we typed; keep what insert() gives back.
		"""
		if not frappe.db.exists("Display Type", "Rack"):
			frappe.get_doc({"doctype": "Display Type", "type_name": "Rack"}).insert()

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

		self.customer = frappe.db.get_value("Customer", {"customer_name": CUSTOMER}, "name")
		if not self.customer:
			self.customer = (
				frappe.get_doc(
					{
						"doctype": "Customer",
						"customer_name": CUSTOMER,
						"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
						"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
					}
				)
				.insert()
				.name
			)

		# a "Warehouse" location is a Warehouse Rack, not an ERPNext Warehouse
		# (transitions.LOCATION_DOCTYPE), so the receipt needs a rack
		self.rack = frappe.db.get_value("Warehouse Rack", {"rack_name": RACK}, "name")
		if not self.rack:
			self.rack = frappe.get_doc({"doctype": "Warehouse Rack", "rack_name": RACK}).insert().name

	def _unit(self):
		return frappe.get_doc(
			{"doctype": "Display Unit", "supplier": self.supplier, "display_type": "Rack"}
		).insert()

	def _move(self, unit, mtype, **kw):
		m = frappe.get_doc(
			{"doctype": "Display Movement", "display_unit": unit.name, "movement_type": mtype, **kw}
		)
		m.insert()
		m.submit()
		return m

	def test_receive_updates_unit(self):
		u = self._unit()
		self._move(u, "Receive at Warehouse", to_location_type="Warehouse", to_location=self.rack)
		u.reload()
		self.assertEqual(u.current_status, "In Warehouse")
		self.assertEqual(u.current_location_type, "Warehouse")

	def test_install_requires_customer(self):
		u = self._unit()
		self._move(u, "Receive at Warehouse", to_location_type="Warehouse", to_location=self.rack)
		with self.assertRaises(frappe.ValidationError):
			self._move(u, "Install at Customer")

	def test_full_install_flow(self):
		u = self._unit()
		self._move(u, "Receive at Warehouse", to_location_type="Warehouse", to_location=self.rack)
		self._move(
			u,
			"Install at Customer",
			customer=self.customer,
			expected_return_date="2027-01-01",
			to_location_type="Customer",
			to_location=self.customer,
		)
		u.reload()
		self.assertEqual(u.current_status, "Installed at Customer")
		self.assertEqual(u.current_customer, self.customer)
		self.assertEqual(str(u.expected_return_date), "2027-01-01")

	def test_illegal_move_blocked(self):
		u = self._unit()
		with self.assertRaises(frappe.ValidationError):
			self._move(u, "Reserve")

	def test_cancel_recomputes_previous_state(self):
		u = self._unit()
		self._move(u, "Receive at Warehouse", to_location_type="Warehouse", to_location=self.rack)
		m2 = self._move(u, "Reserve")
		u.reload()
		self.assertEqual(u.current_status, "Reserved")
		m2.cancel()
		u.reload()
		self.assertEqual(u.current_status, "In Warehouse")
