"""Create workspaces from code without ever overwriting the site's copy.

A workspace shipped as a module file is re-imported on every migrate, so
anything changed in the UI — its roles, icon, cards, order — is lost on
the next app update. These are created only when missing instead.
"""

import json

import frappe


TARGET_DOCTYPE = {"DocType": "DocType", "Report": "Report", "Page": "Page", "Dashboard": "Dashboard"}


def _target_exists(row):
	"""Skip rows pointing at something this site does not have."""
	kind = row.get("link_type") or row.get("type")
	target = row.get("link_to")
	if not target or kind not in TARGET_DOCTYPE:
		return True
	return bool(frappe.db.exists(TARGET_DOCTYPE[kind], target))


def ensure_workspace(spec):
	"""Create the workspace if it isn't there. Returns created/kept."""
	name = spec["name"]
	if frappe.db.exists("Workspace", name):
		return "kept"

	shortcuts = [s for s in spec.get("shortcuts", []) if _target_exists(s)]
	links = [l for l in spec.get("links", []) if l.get("type") == "Card Break" or _target_exists(l)]
	kept_cards = [c for c in spec.get("cards", []) if frappe.db.exists("Number Card", c)]

	doc = frappe.get_doc({
		"doctype": "Workspace",
		"name": name,
		"title": spec.get("title", name),
		"label": spec.get("label", name),
		"module": spec.get("module", "Chundakadan"),
		"public": 1,
		"icon": spec.get("icon"),
		"indicator_color": spec.get("indicator_color"),
		"sequence_id": spec.get("sequence_id", 10),
		"content": json.dumps(spec.get("content", [])),
		"number_cards": [{"label": c, "number_card_name": c} for c in kept_cards],
		"shortcuts": shortcuts,
		"links": links,
		"roles": [{"role": r} for r in spec.get("roles", [])],
	})
	doc.flags.ignore_permissions = True
	doc.flags.ignore_links = True  # a report or doctype may not exist on every site
	doc.flags.name_set = True
	doc.insert(ignore_permissions=True)
	return "created"
