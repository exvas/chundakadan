# Copyright (c) 2026, Chundakadan and contributors
"""How much of each item is lying in the stores.

Balance Qty is the closing stock as on the To Date, read straight from the
Stock Ledger, so it matches Stock Balance. In Qty and Out Qty show what
moved between the From Date and the To Date, which is what the date range
is for -- the balance itself is always "as on To Date".

Group By decides the shape: "Item and Warehouse" gives a row per item per
warehouse, "Item" collapses the warehouses into one row per item. Rows that
never moved and hold nothing are left out.
"""

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("company"):
		frappe.throw(_("Select a Company"))
	if not (filters.get("from_date") and filters.get("to_date")):
		frappe.throw(_("Select From Date and To Date"))
	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be after To Date"))
	return get_columns(filters), get_data(filters)


def group_by_warehouse(filters):
	"""Warehouse-wise rows unless the user asked for a plain item list."""
	return filters.get("group_by") != "Item"


def get_columns(filters=None):
	filters = frappe._dict(filters or {})
	warehouse_column = (
		[{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150}]
		if group_by_warehouse(filters)
		else []
	)
	return [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 110},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 260},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 120},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 140},
		*warehouse_column,
		{"label": _("Balance Qty"), "fieldname": "balance_qty", "fieldtype": "Float", "width": 110},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 70},
		{"label": _("Stock Value"), "fieldname": "stock_value", "fieldtype": "Currency", "width": 130},
		{"label": _("In Qty"), "fieldname": "in_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Out Qty"), "fieldname": "out_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Last Movement"), "fieldname": "last_movement", "fieldtype": "Date", "width": 120},
	]


def get_data(filters):
	conditions = [
		"sle.is_cancelled = 0",
		"sle.company = %(company)s",
		"sle.posting_date <= %(to_date)s",
	]
	if filters.get("warehouse"):
		conditions.append("sle.warehouse = %(warehouse)s")
	if filters.get("item_code"):
		conditions.append("sle.item_code = %(item_code)s")
	if filters.get("brand"):
		conditions.append("item.brand = %(brand)s")
	if filters.get("item_group"):
		conditions.append("item.item_group = %(item_group)s")

	by_warehouse = group_by_warehouse(filters)
	warehouse_select = "sle.warehouse," if by_warehouse else ""
	warehouse_group = ", sle.warehouse" if by_warehouse else ""

	rows = frappe.db.sql(
		f"""
		select
			sle.item_code,
			item.item_name,
			item.brand,
			item.item_group,
			{warehouse_select}
			sum(sle.actual_qty) as balance_qty,
			item.stock_uom as uom,
			sum(sle.stock_value_difference) as stock_value,
			sum(case when sle.posting_date >= %(from_date)s and sle.actual_qty > 0
				then sle.actual_qty else 0 end) as in_qty,
			-sum(case when sle.posting_date >= %(from_date)s and sle.actual_qty < 0
				then sle.actual_qty else 0 end) as out_qty,
			max(case when sle.posting_date >= %(from_date)s then sle.posting_date end) as last_movement
		from `tabStock Ledger Entry` sle
		join `tabItem` item on item.name = sle.item_code
		where {" and ".join(conditions)}
		group by sle.item_code{warehouse_group}
		having balance_qty <> 0 or in_qty <> 0 or out_qty <> 0
		order by item.item_name{warehouse_group}
		""",
		filters,
		as_dict=True,
	)

	if filters.get("hide_zero_balance"):
		rows = [row for row in rows if row.balance_qty]
	return rows
