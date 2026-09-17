"""Number cards for the Dispatch workspace.

The workspace itself ships as a module file (chundakadan/workspace/dispatch).
Cards are upserted on every migrate (after_migrate), so a changed filter here
reaches the site. Filters match the Dispatch page tabs in dispatch/api.py.

Dynamic filters are JS expressions evaluated in the browser by
dashboard_utils.js, not Python.
"""

import json

import frappe

from chundakadan.dispatch import constants as C

MODULE = "Chundakadan"
DT = "Dispatch Log"
NOT_CANCELLED = [DT, "invoice_cancelled", "=", 0]
TODAY_JS = "frappe.datetime.get_today()"

# label, function, aggregate field, filters, dynamic filters, color
CARDS = [
	("Pending Dispatch", "Count", None, [[DT, "dispatch_status", "=", C.PENDING]], None, "#F59E0B"),
	(
		"Pending Over 2 Days",
		"Count",
		None,
		[[DT, "dispatch_status", "=", C.PENDING]],
		[[DT, "posting_date", "<", "frappe.datetime.add_days(frappe.datetime.get_today(), -2)"]],
		"#EF4444",
	),
	(
		"Pending Dispatch Value",
		"Sum",
		"grand_total",
		[[DT, "dispatch_status", "=", C.PENDING]],
		None,
		"#F97316",
	),
	(
		"Delivery Follow-up Today",
		"Count",
		None,
		[[DT, "dispatch_status", "in", [C.DISPATCHED, C.NOT_DELIVERED]]],
		[[DT, "expected_delivery_date", "<=", TODAY_JS]],
		"#8B5CF6",
	),
	("In Transit", "Count", None, [[DT, "dispatch_status", "=", C.DISPATCHED]], None, "#3B82F6"),
	("Dispatched Today", "Count", None, [[DT, "dispatched_on", "Timespan", "today"]], None, "#0EA5E9"),
	(
		"Delivered Today",
		"Count",
		None,
		[
			[DT, "dispatch_status", "in", [C.DELIVERED, C.PICKUP]],
			[DT, "delivery_confirmed_on", "Timespan", "today"],
		],
		None,
		"#22C55E",
	),
	("Not Delivered", "Count", None, [[DT, "dispatch_status", "=", C.NOT_DELIVERED]], None, "#DC2626"),
]


def ensure_dispatch_number_cards(*args, **kwargs):
	for label, function, aggregate, filters, dynamic, color in CARDS:
		values = {
			"label": label,
			"type": "Document Type",
			"document_type": DT,
			"function": function,
			"aggregate_function_based_on": aggregate,
			"filters_json": json.dumps([NOT_CANCELLED, *filters]),
			"dynamic_filters_json": json.dumps(dynamic) if dynamic else None,
			"color": color,
			"is_public": 1,
			"module": MODULE,
		}
		if frappe.db.exists("Number Card", label):
			doc = frappe.get_doc("Number Card", label)
			doc.update(values)
			doc.save(ignore_permissions=True)
		else:
			frappe.get_doc({"doctype": "Number Card", **values}).insert(ignore_permissions=True)
