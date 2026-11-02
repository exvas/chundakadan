"""The customer's own sales person, filled in for them.

Every customer now names a sales person on their Sales Team, so asking the
biller to pick one again on each invoice and each receipt is asking them to
re-enter something the system already knows — and on a Sales Invoice the
field is mandatory, so a forgotten one stops the save.

Filled only when the field is empty. Whoever is on the document has either
been chosen on purpose or carried in from the mobile app, and must not be
overwritten by the customer's default.
"""

import frappe


def sales_person_for_customer(customer: str | None) -> str | None:
	"""The sales person on this customer's Sales Team, if there is one."""
	if not customer:
		return None
	return frappe.db.get_value(
		"Sales Team",
		{"parent": customer, "parenttype": "Customer"},
		"sales_person",
		order_by="idx asc",
	)


def set_sales_person_from_customer(doc, method=None):
	"""Sales Invoice: default the sales person to the customer's own."""
	if doc.get("custom_sales_person"):
		return
	person = sales_person_for_customer(doc.get("customer"))
	if person:
		doc.custom_sales_person = person


@frappe.whitelist()
def get_sales_person_for_customer(customer: str) -> str | None:
	"""For the form, so the box fills the moment a customer is picked.

	A child table cannot be read through frappe.client.get_value, so the
	lookup is exposed here rather than reached for from the browser.
	"""
	frappe.has_permission("Customer", "read", throw=True)
	return sales_person_for_customer(customer)


#: Payment Entry carries two fields labelled "Sales Person": the Link one every
#: report reads, and an older plain-Data one. Both showed on the form, one above
#: the other, with no way to tell which mattered. The Data one is kept — the
#: Cheque Bounce report still reads it and 320 receipts hold a value — but it is
#: hidden, and the server keeps it in step with the Link field.
DUPLICATE_FIELD = "Payment Entry-custom_sales_persons"


def hide_the_duplicate_sales_person_field():
	"""after_migrate: one Sales Person box on the form, not two."""
	if not frappe.db.exists("Custom Field", DUPLICATE_FIELD):
		return
	if frappe.db.get_value("Custom Field", DUPLICATE_FIELD, "hidden"):
		return
	frappe.db.set_value("Custom Field", DUPLICATE_FIELD, "hidden", 1, update_modified=False)
	frappe.clear_cache(doctype="Payment Entry")
	print("chundakadan: hid the duplicate Sales Person field on Payment Entry")
