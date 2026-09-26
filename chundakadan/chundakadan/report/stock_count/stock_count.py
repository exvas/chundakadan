# Copyright (c) 2026, Chundakadan and contributors
"""How much of each item is lying in the stores.

Balance Qty is the closing stock as on the To Date, read straight from the
Stock Ledger, so it matches Stock Balance. In Qty and Out Qty show what
moved between the From Date and the To Date, which is what the date range
is for -- the balance itself is always "as on To Date".

Everything here works off `qty_after_transaction`, never `sum(actual_qty)`.
A Stock Reconciliation writes **actual_qty = 0** and puts the new balance in
`qty_after_transaction`, so summing actual_qty reports zero for any stock
that was set by a reconciliation -- which on a site opened by reconciliation
is nearly every item. The per-row movement is therefore the difference from
the previous row, which is also how ERPNext's own Stock Balance report
handles it.

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
	warehouse_select = "ledger.warehouse," if by_warehouse else ""
	warehouse_group = ", ledger.warehouse" if by_warehouse else ""

	rows = frappe.db.sql(
		f"""
		with ledger as (
			select
				sle.item_code,
				sle.warehouse,
				sle.posting_date,
				sle.qty_after_transaction,
				sle.stock_value,
				sle.qty_after_transaction - coalesce(lag(sle.qty_after_transaction) over (
					partition by sle.item_code, sle.warehouse
					order by sle.posting_date, sle.posting_time, sle.creation
				), 0) as delta,
				row_number() over (
					partition by sle.item_code, sle.warehouse
					order by sle.posting_date desc, sle.posting_time desc, sle.creation desc
				) as newest
			from `tabStock Ledger Entry` sle
			join `tabItem` item on item.name = sle.item_code
			where {" and ".join(conditions)}
		)
		select
			ledger.item_code,
			item.item_name,
			item.brand,
			item.item_group,
			{warehouse_select}
			sum(case when ledger.newest = 1 then ledger.qty_after_transaction else 0 end) as balance_qty,
			item.stock_uom as uom,
			sum(case when ledger.newest = 1 then ledger.stock_value else 0 end) as stock_value,
			sum(case when ledger.posting_date >= %(from_date)s and ledger.delta > 0
				then ledger.delta else 0 end) as in_qty,
			-sum(case when ledger.posting_date >= %(from_date)s and ledger.delta < 0
				then ledger.delta else 0 end) as out_qty,
			max(case when ledger.posting_date >= %(from_date)s then ledger.posting_date end) as last_movement
		from ledger
		join `tabItem` item on item.name = ledger.item_code
		group by ledger.item_code{warehouse_group}
		having balance_qty <> 0 or in_qty <> 0 or out_qty <> 0
		order by item.item_name{warehouse_group}
		""",
		filters,
		as_dict=True,
	)

	if filters.get("hide_zero_balance"):
		rows = [row for row in rows if row.balance_qty]
	return rows
