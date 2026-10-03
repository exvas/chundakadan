"""Keep an Address's second line showing the customer's territory.

The sales team reads a territory off the address line in print formats and
listings, so Address Line 2 carries it. It is derived, not typed: the
Customer's Territory is the only source, and the address follows it --
when the address is saved and whenever the customer's territory changes.
"""

import frappe

FIELD = "address_line2"


def territory_of(customer: str | None) -> str | None:
	if not customer:
		return None
	return frappe.db.get_value("Customer", customer, "territory")


def customer_of(doc) -> str | None:
	"""The customer this address belongs to, if any.

	An address can be linked to several parties; the customer is the one
	whose territory we follow, and the first customer link wins.
	"""
	for link in doc.get("links") or []:
		if link.link_doctype == "Customer":
			return link.link_name
	return None


def set_line2_from_territory(doc, method=None):
	"""Address validate — the line follows the customer's territory."""
	territory = territory_of(customer_of(doc))
	if territory:
		doc.set(FIELD, territory)


def sync_addresses_to_territory(doc, method=None):
	"""Customer on_update — a changed territory re-stamps every address.

	Written straight to the column: an Address save would re-run India
	Compliance's GSTIN and state checks on records nobody touched, and a
	customer changing territory must not fail over somebody else's
	half-filled address.
	"""
	before = doc.get_doc_before_save()
	if before and before.get("territory") == doc.get("territory"):
		return
	if not doc.get("territory"):
		return
	for name in addresses_of(doc.name):
		if frappe.db.get_value("Address", name, FIELD) == doc.territory:
			continue
		frappe.db.set_value("Address", name, FIELD, doc.territory, update_modified=False)


def addresses_of(customer: str) -> list[str]:
	return frappe.db.get_all(
		"Dynamic Link",
		filters={"link_doctype": "Customer", "link_name": customer, "parenttype": "Address"},
		pluck="parent",
	)
