import frappe

from chundakadan.doc_events.sales_person_default import sales_person_for_customer


def set_custom_sales_person(doc, method=None):
	"""Name whose receipt this is, without the collector retyping it.

	`custom_sales_person` is the field every report reads. The older
	`custom_sales_persons` (a plain Data field with the same label) is kept in
	step only because the Cheque Bounce report still reads it; nothing new
	should be written to it alone.

	The customer's own sales person comes first: a receipt is entered against
	a customer long before it is allocated to an invoice, and often against
	several invoices at once. An allocated invoice is the fallback, for a
	payment whose customer has nobody.
	"""
	if not doc.custom_sales_person:
		person = None
		if doc.party_type == "Customer":
			person = sales_person_for_customer(doc.party)
		if not person:
			person = _sales_person_of_an_allocated_invoice(doc)
		if person:
			doc.custom_sales_person = person

	# keep the older duplicate in step for the Cheque Bounce report
	if doc.custom_sales_person and not doc.custom_sales_persons:
		doc.custom_sales_persons = doc.custom_sales_person


def _sales_person_of_an_allocated_invoice(doc):
	for ref in doc.references or []:
		if ref.reference_doctype == "Sales Invoice" and ref.reference_name:
			person = frappe.db.get_value("Sales Invoice", ref.reference_name, "custom_sales_person")
			if person:
				return person
	return None


def validate_check_bounce(doc, method=None):
	if doc.custom_check_bounce:
		frappe.throw("Cannot submit Payment Entry because cheque bounce is checked.")
