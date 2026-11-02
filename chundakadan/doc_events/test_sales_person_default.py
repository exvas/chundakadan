"""The customer's sales person should already be in the box."""

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events.payment_entry import set_custom_sales_person
from chundakadan.doc_events.sales_person_default import (
	DUPLICATE_FIELD,
	hide_the_duplicate_sales_person_field,
	sales_person_for_customer,
	set_sales_person_from_customer,
)

CUSTOMER = "_Test CDN Sales Person Customer"
PERSON = "_Test CDN Seller"
OTHER = "_Test CDN Other Seller"


def ensure_sales_person(name):
	if not frappe.db.exists("Sales Person", name):
		frappe.get_doc(
			{
				"doctype": "Sales Person",
				"sales_person_name": name,
				"parent_sales_person": "Sales Team",
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
	return name


def ensure_customer(name, person=None):
	# the site names customers by its own series, not by the customer name
	docname = frappe.db.get_value("Customer", {"customer_name": name}, "name")
	if not docname:
		docname = (
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": name,
					"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
					"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	doc = frappe.get_doc("Customer", docname)
	doc.set("sales_team", [])
	if person:
		doc.append("sales_team", {"sales_person": person, "allocated_percentage": 100})
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.name


def invoice(**values):
	return frappe._dict({"doctype": "Sales Invoice", "customer": None, "custom_sales_person": None, **values})


def receipt(**values):
	return frappe._dict(
		{
			"doctype": "Payment Entry",
			"party_type": "Customer",
			"party": None,
			"custom_sales_person": None,
			"custom_sales_persons": None,
			"references": [],
			**values,
		}
	)


class TestSalesPersonDefault(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_sales_person(PERSON)
		ensure_sales_person(OTHER)
		cls.customer = ensure_customer(CUSTOMER, PERSON)
		cls.nobody = ensure_customer(CUSTOMER + " Nobody")

	def test_the_customer_names_their_sales_person(self):
		self.assertEqual(sales_person_for_customer(self.customer), PERSON)

	def test_a_customer_with_nobody_names_nobody(self):
		self.assertIsNone(sales_person_for_customer(self.nobody))
		self.assertIsNone(sales_person_for_customer(None))

	# --- Sales Invoice -----------------------------------------------------
	def test_an_invoice_gets_the_customer_sales_person(self):
		doc = invoice(customer=self.customer)
		set_sales_person_from_customer(doc)
		self.assertEqual(doc.custom_sales_person, PERSON)

	def test_one_already_chosen_is_never_overwritten(self):
		doc = invoice(customer=self.customer, custom_sales_person=OTHER)
		set_sales_person_from_customer(doc)
		self.assertEqual(doc.custom_sales_person, OTHER, "the biller's own choice must stand")

	def test_a_customer_with_nobody_leaves_it_empty(self):
		doc = invoice(customer=self.nobody)
		set_sales_person_from_customer(doc)
		self.assertIsNone(doc.custom_sales_person)

	# --- Payment Entry -----------------------------------------------------
	def test_a_receipt_gets_it_from_the_customer(self):
		doc = receipt(party=self.customer)
		set_custom_sales_person(doc)
		self.assertEqual(doc.custom_sales_person, PERSON)

	def test_a_receipt_keeps_the_one_it_came_with(self):
		doc = receipt(party=self.customer, custom_sales_person=OTHER)
		set_custom_sales_person(doc)
		self.assertEqual(doc.custom_sales_person, OTHER)

	def test_the_older_duplicate_is_kept_in_step(self):
		"""The Cheque Bounce report still reads it."""
		doc = receipt(party=self.customer)
		set_custom_sales_person(doc)
		self.assertEqual(doc.custom_sales_persons, PERSON)

	def test_a_supplier_payment_is_not_given_a_sales_person(self):
		doc = receipt(party_type="Supplier", party=self.customer)
		set_custom_sales_person(doc)
		self.assertIsNone(doc.custom_sales_person)


class TestOnlyOneSalesPersonBox(FrappeTestCase):
	"""Payment Entry showed two fields with the same label, one above the
	other. The older one is kept for the Cheque Bounce report, but out of
	sight — nobody can tell two identical boxes apart."""

	def test_the_duplicate_is_hidden(self):
		if not frappe.db.exists("Custom Field", DUPLICATE_FIELD):
			self.skipTest("this site never had the duplicate")
		frappe.db.set_value("Custom Field", DUPLICATE_FIELD, "hidden", 0, update_modified=False)

		hide_the_duplicate_sales_person_field()

		self.assertEqual(frappe.db.get_value("Custom Field", DUPLICATE_FIELD, "hidden"), 1)

	def test_running_it_twice_is_harmless(self):
		if not frappe.db.exists("Custom Field", DUPLICATE_FIELD):
			self.skipTest("this site never had the duplicate")
		hide_the_duplicate_sales_person_field()
		hide_the_duplicate_sales_person_field()
		self.assertEqual(frappe.db.get_value("Custom Field", DUPLICATE_FIELD, "hidden"), 1)

	def test_the_field_itself_is_never_deleted(self):
		"""320 receipts hold a value in it and a report still reads it."""
		if not frappe.db.exists("Custom Field", DUPLICATE_FIELD):
			self.skipTest("this site never had the duplicate")
		hide_the_duplicate_sales_person_field()
		self.assertTrue(frappe.db.exists("Custom Field", DUPLICATE_FIELD))
