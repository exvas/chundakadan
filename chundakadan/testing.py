"""Helpers for tests that need the bench to look like a working one.

Several test modules hard-coded the live company, so on any bench that is not
the live site — CI, or a developer's fresh one — they failed with
"Could not find Company: Chundakadan Agencies" before testing anything. The
behaviour they cover is not company-specific, so they only need *a* company.

Not named test_* on purpose: Frappe's runner collects those as test modules.
"""

import frappe

LIVE_COMPANY = "Chundakadan Agencies"
TEST_SUPPLIER = "_Test CDN Supplier"
TEST_CUSTOMER = "_Test CDN Customer"


def a_company() -> str | None:
	"""The live company where the bench has it, otherwise any company."""
	if frappe.db.exists("Company", LIVE_COMPANY):
		return LIVE_COMPANY
	# order_by: an unordered get_value sorts by `modified`, so two calls in
	# one test could land on two different companies -- which is how a test
	# employee ended up in a company other than the one the test was using.
	return frappe.db.get_value("Company", {}, "name", order_by="name asc")


def a_warehouse(company: str) -> str | None:
	return frappe.db.get_value(
		"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name", order_by="name asc"
	)


def a_supplier(company: str | None = None) -> str | None:
	"""A supplier of our own, billed in the company's currency.

	Reading one off the bench kept landing on erpnext's USD test supplier,
	and every invoice then died on "Party Account Creditors - _TC currency
	(INR) and document currency (USD) should be same" -- a currency
	mismatch that says nothing about the behaviour under test. Two rounds
	of filtering only moved which wrong supplier came back, so the tests
	bring their own.
	"""
	existing = frappe.db.get_value("Supplier", {"supplier_name": TEST_SUPPLIER}, "name")
	if existing:
		return existing
	group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name", order_by="name asc")
	if not group:
		return None
	doc = frappe.get_doc({"doctype": "Supplier", "supplier_name": TEST_SUPPLIER, "supplier_group": group})
	if company:
		doc.default_currency = frappe.get_cached_value("Company", company, "default_currency")
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	return doc.name


def a_customer(company: str | None = None) -> str | None:
	"""A customer of our own, billed in the company's currency.

	Same reason as a_supplier(): a bench carrying erpnext's test records has
	customers on it in another currency, and a payment read off one came back
	multiplied by the exchange rate -- a figure that looks like a bug in the
	report and is not.
	"""
	existing = frappe.db.get_value("Customer", {"customer_name": TEST_CUSTOMER}, "name")
	if existing:
		return existing
	group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name", order_by="name asc")
	territory = frappe.db.get_value("Territory", {"is_group": 0}, "name", order_by="name asc")
	if not (group and territory):
		return None
	doc = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": TEST_CUSTOMER,
			"customer_group": group,
			"territory": territory,
		}
	)
	if company:
		doc.default_currency = frappe.get_cached_value("Company", company, "default_currency")
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	return doc.name


def a_stock_item() -> str | None:
	return frappe.db.get_value(
		"Item", {"is_stock_item": 1, "disabled": 0, "has_variants": 0}, "name", order_by="name asc"
	)
