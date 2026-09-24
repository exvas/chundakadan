# Copyright (c) 2026, Chundakadan and contributors
"""Every Item that already exists counts as approved.

Item Approval only judges what is created after it is switched on. Without
this, the day the switch is ticked every item on the site would read
"Pending" and the approver would face a list of thousands.

Only the status is written. `disabled` is left exactly as it is, so items
somebody disabled on purpose stay disabled.
"""

import frappe

from chundakadan.doc_events.item_approval import ensure_item_approval_fields


def execute():
	ensure_item_approval_fields()
	if not frappe.db.has_column("Item", "custom_approval_status"):
		return
	frappe.db.sql(
		"""update `tabItem`
		set custom_approval_status = 'Approved'
		where custom_approval_status is null or custom_approval_status = ''"""
	)
