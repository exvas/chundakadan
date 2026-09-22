# Copyright (c) 2026, Chundakadan and contributors
"""Sales by brand for a date range — the pivot the sales team keeps in Excel.

One row per brand: what was sold, less any credit notes in the same range.
"""

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not (filters.from_date and filters.to_date):
		frappe.throw(_("Select From Date and To Date"))
	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be after To Date"))
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 200},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 160},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": _("Invoices"), "fieldname": "invoices", "fieldtype": "Int", "width": 90},
		{"label": _("Customers"), "fieldname": "customers", "fieldtype": "Int", "width": 100},
	]


def get_data(filters):
	conditions = [
		"si.docstatus = 1",
		"si.company = %(company)s",
		"si.posting_date between %(from_date)s and %(to_date)s",
	]
	if filters.get("sales_person"):
		conditions.append("si.custom_sales_person = %(sales_person)s")
	if filters.get("brand"):
		conditions.append("item.brand = %(brand)s")
	if filters.get("customer"):
		conditions.append("si.customer = %(customer)s")

	return frappe.db.sql(
		f"""
		select
			coalesce(nullif(item.brand, ''), '{_("Without Brand")}') as brand,
			sum(sii.base_net_amount) as amount,
			sum(sii.stock_qty) as qty,
			count(distinct si.name) as invoices,
			count(distinct si.customer) as customers
		from `tabSales Invoice Item` sii
		join `tabSales Invoice` si on si.name = sii.parent
		join `tabItem` item on item.name = sii.item_code
		where {" and ".join(conditions)}
		group by coalesce(nullif(item.brand, ''), '{_("Without Brand")}')
		order by amount desc
		""",
		filters,
		as_dict=True,
	)
