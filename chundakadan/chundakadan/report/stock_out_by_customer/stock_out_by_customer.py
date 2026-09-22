# Copyright (c) 2026, Chundakadan and contributors
"""What left the stores, and which customer took it.

Reads the Stock Ledger, so it counts the stock that actually moved —
Delivery Notes, and the few Sales Invoices that update stock themselves.
Returns are negative rows, so they net off.
"""

import frappe
from frappe import _

# stock leaves against a customer through these only
VOUCHER_TYPES = ("Delivery Note", "Sales Invoice")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not (filters.from_date and filters.to_date):
		frappe.throw(_("Select From Date and To Date"))
	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be after To Date"))
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 110},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 240},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 110},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 100},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 230},
		{"label": _("Qty Out"), "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 70},
		{"label": _("Value"), "fieldname": "value", "fieldtype": "Currency", "width": 120},
		{"label": _("Vouchers"), "fieldname": "vouchers", "fieldtype": "Int", "width": 90},
		{"label": _("Last Out On"), "fieldname": "last_out_on", "fieldtype": "Date", "width": 100},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 130},
	]


def get_data(filters):
	conditions = [
		"sle.is_cancelled = 0",
		"sle.company = %(company)s",
		"sle.posting_date between %(from_date)s and %(to_date)s",
		"sle.voucher_type in %(voucher_types)s",
	]
	filters.voucher_types = VOUCHER_TYPES
	if filters.get("customer"):
		conditions.append("coalesce(dn.customer, si.customer) = %(customer)s")
	if filters.get("item_code"):
		conditions.append("sle.item_code = %(item_code)s")
	if filters.get("warehouse"):
		conditions.append("sle.warehouse = %(warehouse)s")
	if filters.get("brand"):
		conditions.append("item.brand = %(brand)s")
	if filters.get("sales_person"):
		conditions.append("coalesce(dn.custom_sales_person, si.custom_sales_person) = %(sales_person)s")

	return frappe.db.sql(
		f"""
		select
			sle.item_code,
			item.item_name,
			item.brand,
			coalesce(dn.customer, si.customer) as customer,
			coalesce(dn.customer_name, si.customer_name) as customer_name,
			-sum(sle.actual_qty) as qty,
			item.stock_uom as uom,
			-sum(sle.stock_value_difference) as value,
			count(distinct sle.voucher_no) as vouchers,
			max(sle.posting_date) as last_out_on,
			sle.warehouse
		from `tabStock Ledger Entry` sle
		join `tabItem` item on item.name = sle.item_code
		left join `tabDelivery Note` dn on sle.voucher_type = 'Delivery Note' and dn.name = sle.voucher_no
		left join `tabSales Invoice` si on sle.voucher_type = 'Sales Invoice' and si.name = sle.voucher_no
		where {" and ".join(conditions)}
			and coalesce(dn.customer, si.customer) is not null
		group by sle.item_code, coalesce(dn.customer, si.customer), sle.warehouse
		having qty <> 0
		order by qty desc
		""",
		filters,
		as_dict=True,
	)
