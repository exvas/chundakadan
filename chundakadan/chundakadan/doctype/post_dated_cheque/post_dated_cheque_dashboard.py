from frappe import _


def get_data():
	"""Connections: the payments this cheque became, and its bounce entry.

	Payment Entries point back with custom_post_dated_cheque, so both the
	collection and the return show up; an internal link could only follow
	one field.
	"""
	return {
		"fieldname": "custom_post_dated_cheque",
		"internal_links": {
			"Cheque Bounce": "cheque_bounce",
		},
		"transactions": [
			{"label": _("Payments"), "items": ["Payment Entry"]},
			{"label": _("Bounce"), "items": ["Cheque Bounce"]},
		],
	}
