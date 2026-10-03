import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events.address_territory import (
	addresses_of,
	customer_of,
	set_line2_from_territory,
	territory_of,
)

COMPANY = "Chundakadan Agencies"


class AddressTerritoryCase(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.first = self._territory("CDN Test Territory A")
		self.second = self._territory("CDN Test Territory B")
		self.customer = self._customer(self.first)

	def tearDown(self):
		frappe.db.rollback()

	def _territory(self, name):
		if not frappe.db.exists("Territory", name):
			frappe.get_doc({
				"doctype": "Territory",
				"territory_name": name,
				"is_group": 0,
				"parent_territory": frappe.db.get_value("Territory", {"is_group": 1}, "name"),
			}).insert(ignore_permissions=True)
		return name

	def _customer(self, territory):
		return frappe.get_doc({
			"doctype": "Customer",
			"customer_name": "CDN Address Territory Co",
			"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
			"customer_type": "Company",
			"territory": territory,
		}).insert(ignore_permissions=True)

	def _address(self, customer=None, **values):
		doc = frappe.get_doc({
			"doctype": "Address",
			"address_title": "CDN Address Territory",
			"address_type": "Billing",
			"address_line1": "8/243A, Thrissur Road",
			"city": "Changaramkulam",
			"state": "Kerala",
			"country": "India",
			"pincode": "679575",
			"links": [{"link_doctype": "Customer", "link_name": (customer or self.customer.name)}],
			**values,
		})
		doc.insert(ignore_permissions=True)
		return doc


class TestTheAddressFollowsTheCustomer(AddressTerritoryCase):
	def test_a_new_address_carries_the_territory(self):
		address = self._address()
		self.assertEqual(address.address_line2, self.first)

	def test_whatever_was_typed_in_line_two_is_replaced(self):
		"""The line is derived, not typed -- the territory is the source."""
		address = self._address(address_line2="Near the temple")
		self.assertEqual(address.address_line2, self.first)

	def test_changing_the_territory_restamps_every_address(self):
		one = self._address()
		two = self._address(address_type="Shipping")
		self.customer.territory = self.second
		self.customer.save()
		self.assertEqual(frappe.db.get_value("Address", one.name, "address_line2"), self.second)
		self.assertEqual(frappe.db.get_value("Address", two.name, "address_line2"), self.second)

	def test_saving_the_customer_without_touching_the_territory_changes_nothing(self):
		address = self._address()
		frappe.db.set_value("Address", address.name, "address_line2", "left alone", update_modified=False)
		self.customer.customer_name = "CDN Address Territory Co Ltd"
		self.customer.save()
		self.assertEqual(frappe.db.get_value("Address", address.name, "address_line2"), "left alone")

	def test_an_address_with_no_customer_is_left_alone(self):
		supplier = frappe.db.get_value("Supplier", {}, "name")
		if not supplier:
			self.skipTest("no supplier to link")
		doc = frappe.get_doc({
			"doctype": "Address",
			"address_title": "CDN Supplier Address",
			"address_type": "Billing",
			"address_line1": "Market Road",
			"address_line2": "Opposite the bank",
			"city": "Calicut",
			"state": "Kerala",
			"country": "India",
			"pincode": "673001",
			"links": [{"link_doctype": "Supplier", "link_name": supplier}],
		}).insert(ignore_permissions=True)
		self.assertEqual(doc.address_line2, "Opposite the bank")

	def test_a_customer_with_no_territory_leaves_the_line_as_typed(self):
		frappe.db.set_value("Customer", self.customer.name, "territory", None, update_modified=False)
		address = self._address(address_line2="Near the temple")
		self.assertEqual(address.address_line2, "Near the temple")


class TestTheHelpers(AddressTerritoryCase):
	def test_the_customer_link_is_found(self):
		address = self._address()
		self.assertEqual(customer_of(address), self.customer.name)

	def test_territory_of_reads_the_customer(self):
		self.assertEqual(territory_of(self.customer.name), self.first)
		self.assertIsNone(territory_of(None))

	def test_addresses_of_lists_them(self):
		one = self._address()
		self.assertIn(one.name, addresses_of(self.customer.name))

	def test_set_line2_is_safe_on_an_unlinked_address(self):
		doc = frappe.new_doc("Address")
		doc.address_line2 = "untouched"
		set_line2_from_territory(doc)
		self.assertEqual(doc.address_line2, "untouched")
