"""Help the user line up an Address State with the GSTIN they typed.

India Compliance refuses to save when the GSTIN's first two digits don't
match the State — right, but it doesn't say which State the GSTIN belongs
to, and the user has to know the code table. This only *tells* the form;
the user decides whether to change the State.
"""

import frappe
from frappe import _


@frappe.whitelist()
def state_for_gstin(gstin):
	"""The State a GSTIN belongs to, from its first two digits."""
	gstin = (gstin or "").strip().upper()
	if len(gstin) < 2 or not gstin[:2].isdigit():
		return None

	from india_compliance.gst_india.constants import STATE_NUMBERS

	for state, number in STATE_NUMBERS.items():
		if number == gstin[:2]:
			return state
	return None


@frappe.whitelist()
def set_state_from_gstin(address):
	"""Set the Address State to the one its GSTIN belongs to."""
	doc = frappe.get_doc("Address", address)
	doc.check_permission("write")
	state = state_for_gstin(doc.gstin)
	if not state:
		frappe.throw(_("{0} is not a state code we know.").format((doc.gstin or "")[:2] or "—"))
	if doc.state == state:
		return {"state": state, "changed": False}
	doc.state = state
	doc.save()
	return {"state": state, "changed": True}
