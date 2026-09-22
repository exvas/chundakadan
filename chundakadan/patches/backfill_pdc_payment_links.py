import frappe

from chundakadan.chundakadan.doctype.post_dated_cheque.post_dated_cheque import (
	PE_FIELD,
	ensure_payment_entry_field,
)


def execute():
	"""Point existing Payment Entries back at their cheque.

	Cheques made before the field existed link their payments one way
	only, so the Connections panel showed the collection and missed the
	return.
	"""
	if not frappe.db.exists("DocType", "Post Dated Cheque"):
		return

	ensure_payment_entry_field()

	for cheque in frappe.get_all(
		"Post Dated Cheque",
		filters={"docstatus": ["<", 2]},
		fields=["name", "payment_entry", "return_payment_entry"],
	):
		for payment in (cheque.payment_entry, cheque.return_payment_entry):
			if payment and frappe.db.exists("Payment Entry", payment):
				frappe.db.set_value("Payment Entry", payment, PE_FIELD, cheque.name, update_modified=False)
