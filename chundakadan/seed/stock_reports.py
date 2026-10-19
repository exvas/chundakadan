"""Put our Stock Count report where people look for stock.

ERPNext's own Stock Balance reads a Stock Reconciliation by summing
`actual_qty`, which is 0 on a reconciliation row -- the real figure is in
`qty_after_transaction`. On this site, where every item's opening came
from the 13-09 reconciliation, that makes 1,078 of 4,521 rows show a
negative balance for stock that is perfectly healthy: item 7363 reads
-520 there and 669 in its Bin. Our Stock Count report reads the right
column and returns no negatives at all.

So the right report is one click away, under Stock Reports, instead of
people finding the wrong one first. Re-applied on every migrate because
an erpnext update re-syncs that workspace from its own JSON and would
drop the link.
"""

import frappe

WORKSPACE = "Stock"
CARD_BREAK = "Stock Reports"
REPORT = "Stock Count"


def ensure_stock_count_link(*args, **kwargs):
	"""after_migrate — Stock Count sits with the other stock reports."""
	if not frappe.db.exists("Workspace", WORKSPACE):
		return
	if not frappe.db.exists("Report", REPORT):
		return

	ws = frappe.get_doc("Workspace", WORKSPACE)
	if any(row.link_to == REPORT for row in ws.links):
		return

	rows = list(ws.links)
	start = next(
		(i for i, r in enumerate(rows) if r.type == "Card Break" and r.label == CARD_BREAK),
		None,
	)
	if start is None:
		return
	end = next(
		(i for i in range(start + 1, len(rows)) if rows[i].type == "Card Break"),
		len(rows),
	)
	rows[start].link_count = (rows[start].link_count or 0) + 1

	new_row = {
		"type": "Link",
		"link_type": "Report",
		"link_to": REPORT,
		"label": REPORT,
		"is_query_report": 1,
		"report_ref_doctype": "Stock Ledger Entry",
		"hidden": 0,
		"link_count": 0,
		"onboard": 0,
	}
	ordered = [r.as_dict() for r in rows[:end]] + [new_row] + [r.as_dict() for r in rows[end:]]
	ws.set("links", [])
	for position, row in enumerate(ordered, start=1):
		row = dict(row)
		row.pop("name", None)
		# number them ourselves: a row with a stale idx, or none at all as the
		# new one has, is sorted back out of place on save
		row["idx"] = position
		ws.append("links", row)
	ws.save(ignore_permissions=True)
