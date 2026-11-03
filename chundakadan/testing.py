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
	return frappe.db.get_value("Company", {}, "name")


def a_warehouse(company: str) -> str | None:
	return frappe.db.get_value("Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name")


def a_supplier() -> str | None:
	return frappe.db.get_value("Supplier", {"disabled": 0}, "name")


def a_stock_item() -> str | None:
	return frappe.db.get_value("Item", {"is_stock_item": 1, "disabled": 0, "has_variants": 0}, "name")
