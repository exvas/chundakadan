from frappe import _


def get_data():
	"""Connections: the Payment Entry this cheque became, and its bounce entry."""
	return {
		"fieldname": "name",
		# a plain fieldname on this document — a list means [child table, field]
		"internal_links": {
			"Payment Entry": "payment_entry",
			"Cheque Bounce": "cheque_bounce",
		},
		"transactions": [
			{"label": _("Collection"), "items": ["Payment Entry"]},
			{"label": _("Bounce"), "items": ["Cheque Bounce"]},
		],
	}
