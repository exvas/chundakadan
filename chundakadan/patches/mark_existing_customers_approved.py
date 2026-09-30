# Copyright (c) 2026, Chundakadan and contributors
"""Every Customer that already exists counts as approved.

Customer Approval only judges what is created after it is switched on.
Without this, the day the switch is ticked all 2,183 customers would read
"Pending" and the approver would face an impossible list.

Only the status is written. `disabled` is left exactly as it is.
"""

import frappe

from chundakadan.doc_events.customer_approval import ensure_customer_approval_fields


def execute():
	ensure_customer_approval_fields()
	if not _column_exists("Customer"):
		# has_column() answers from a cached column list, which is stale right
		# after the custom field is created -- ask the database itself
		return
	frappe.db.sql(
		"""update `tabCustomer`
		set custom_approval_status = 'Approved'
		where custom_approval_status is null or custom_approval_status = ''"""
	)


def _column_exists(doctype):
	return bool(
		frappe.db.sql(
			"""select 1 from information_schema.columns
			where table_schema = database() and table_name = %s
			  and column_name = 'custom_approval_status'""",
			f"tab{doctype}",
		)
	)
