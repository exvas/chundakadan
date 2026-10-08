"""Put the grievance card and list on the Approvals workspace.

The workspace is seeded create-if-missing, so that role and icon changes
made in the UI survive an app update. The cost is that a card added to
the spec never reaches a site that already has the workspace -- this
patch carries it across, once.

Idempotent: it checks for the card and the link before adding either.
"""

import json

import frappe

WORKSPACE = "Approvals"
CARD = "Grievances Open"
DOCTYPE = "Employee Grievance"


def execute():
	if not frappe.db.exists("Workspace", WORKSPACE) or not frappe.db.exists("DocType", DOCTYPE):
		return

	from chundakadan.seed.approvals import ensure_approval_number_cards

	ensure_approval_number_cards()
	if not frappe.db.exists("Number Card", CARD):
		return

	ws = frappe.get_doc("Workspace", WORKSPACE)
	changed = False

	if not any(row.number_card_name == CARD for row in ws.number_cards):
		ws.append("number_cards", {"number_card_name": CARD, "label": CARD})
		changed = True

	content = json.loads(ws.content or "[]")
	if not any(
		block.get("type") == "number_card"
		and block.get("data", {}).get("number_card_name") == CARD
		for block in content
	):
		last = _last_number_card_index(content)
		content.insert(last + 1, {
			"id": "ap_nc_griev",
			"type": "number_card",
			"data": {"number_card_name": CARD, "col": 3},
		})
		ws.content = json.dumps(content)
		changed = True

	if not any(row.link_to == DOCTYPE for row in ws.links):
		_add_link_under(ws, "Approvals", DOCTYPE)
		changed = True

	if changed:
		# no explicit commit: the patch runner commits, and committing from
		# here would also make a test run persist whatever it did
		ws.save(ignore_permissions=True)


def _last_number_card_index(content):
	"""Keep the new card beside the others, not after the link sections."""
	last = -1
	for i, block in enumerate(content):
		if block.get("type") == "number_card":
			last = i
	return last if last >= 0 else len(content) - 1


def _add_link_under(ws, card_break_label, doctype):
	"""Insert the link as the last one of its Card Break, and count it."""
	rows = list(ws.links)
	start = None
	for i, row in enumerate(rows):
		if row.type == "Card Break" and row.label == card_break_label:
			start = i
			break
	if start is None:
		return
	end = len(rows)
	for i in range(start + 1, len(rows)):
		if rows[i].type == "Card Break":
			end = i
			break
	rows[start].link_count = (rows[start].link_count or 0) + 1

	new_row = {
		"type": "Link", "link_type": "DocType", "link_to": doctype,
		"label": doctype, "hidden": 0, "is_query_report": 0,
		"link_count": 0, "onboard": 0,
	}
	ordered = [r.as_dict() for r in rows[:end]] + [new_row] + [r.as_dict() for r in rows[end:]]
	ws.set("links", [])
	for position, row in enumerate(ordered, start=1):
		row = dict(row)
		row.pop("name", None)
		# number the rows ourselves: a dict carrying an old idx (or none at
		# all, as the new row does) gets sorted back out of place on save
		row["idx"] = position
		ws.append("links", row)
