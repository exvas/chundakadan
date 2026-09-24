# Copyright (c) 2026, Chundakadan and contributors
# For license information, please see license.txt
"""Which customers bought an item, and how much, in a date range.

One row per item and customer from submitted Sales Invoices. Credit notes
carry negative quantities, so the quantity is net of returns. Brand and item
group come from the Item master (current values), quantity is in the item's
stock UOM so different selling units add up correctly.
"""

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if filters.from_date and filters.to_date and filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be after To Date"))
	return get_columns(filters), get_data(filters)


def group_by_customer(filters):
	"""Customer-wise rows unless the user asked for one row per item."""
	return filters.get("group_by") != "Item"


def get_columns(filters=None):
	filters = frappe._dict(filters or {})
	customer_columns = (
		[
			{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 110},
			{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 240},
		]
		if group_by_customer(filters)
		else []
	)
	return [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 110},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 240},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 110},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 140},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 70},
		*customer_columns,
		{"label": _("Qty Sold"), "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Invoices"), "fieldname": "invoices", "fieldtype": "Int", "width": 80},
		{"label": _("Last Sold On"), "fieldname": "last_sold_on", "fieldtype": "Date", "width": 100},
	]


def get_data(filters):
	conditions = ["si.docstatus = 1", "si.company = %(company)s", "si.posting_date between %(from_date)s and %(to_date)s"]
	for key, column in (
		("item_code", "sii.item_code"),
		("customer", "si.customer"),
		("brand", "item.brand"),
	):
		if filters.get(key):
			conditions.append(f"{column} = %({key})s")
	if filters.get("item_group"):
		lft, rgt = frappe.db.get_value("Item Group", filters.item_group, ["lft", "rgt"])
		conditions.append("item.item_group in (select name from `tabItem Group` where lft >= %(ig_lft)s and rgt <= %(ig_rgt)s)")
		filters.ig_lft, filters.ig_rgt = lft, rgt

	by_customer = group_by_customer(filters)
	customer_select = "si.customer,\n\t\t\tsi.customer_name," if by_customer else ""
	customer_group = ", si.customer" if by_customer else ""

	return frappe.db.sql(
		f"""
		select
			sii.item_code,
			item.item_name,
			item.brand,
			item.item_group,
			item.stock_uom as uom,
			{customer_select}
			sum(sii.stock_qty) as qty,
			sum(sii.base_net_amount) as amount,
			count(distinct si.name) as invoices,
			max(si.posting_date) as last_sold_on
		from `tabSales Invoice Item` sii
		join `tabSales Invoice` si on si.name = sii.parent
		join `tabItem` item on item.name = sii.item_code
		where {" and ".join(conditions)}
		group by sii.item_code{customer_group}
		order by sii.item_code, qty desc
		""",
		filters,
		as_dict=True,
	)
