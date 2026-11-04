"""Helpers for tests that need the bench to look like a working one.

Several test modules hard-coded the live company, so on any bench that is not
the live site — CI, or a developer's fresh one — they failed with
"Could not find Company: Chundakadan Agencies" before testing anything. The
behaviour they cover is not company-specific, so they only need *a* company.

Not named test_* on purpose: Frappe's runner collects those as test modules.
"""

import frappe

LIVE_COMPANY = "Chundakadan Agencies"


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
	"""A supplier that can be billed in the company's own currency.

	A bench carrying erpnext's test records has suppliers in USD on it, and
	an unordered pick landed on one: every invoice then died on "Party
	Account Creditors - _TC currency (INR) and document currency (USD)
	should be same", which says nothing about the behaviour under test.

	The currency test is done here rather than in the query because SQL's
	IN never matches NULL, and the supplier that bills in the company's
	currency is usually the one that never set a currency at all.
	"""
	rows = frappe.get_all(
		"Supplier", filters={"disabled": 0}, fields=["name", "default_currency"], order_by="name asc"
	)
	currency = frappe.get_cached_value("Company", company, "default_currency") if company else None
	if not currency:
		return rows[0].name if rows else None
	for row in rows:
		if not row.default_currency or row.default_currency == currency:
			return row.name
	return None


def a_stock_item() -> str | None:
	return frappe.db.get_value(
		"Item", {"is_stock_item": 1, "disabled": 0, "has_variants": 0}, "name", order_by="name asc"
	)
