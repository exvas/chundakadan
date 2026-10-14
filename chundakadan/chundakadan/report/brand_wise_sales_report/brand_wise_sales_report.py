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
		# the office reads every sales figure with the tax in it, and
		# Sales & Collection Summary already does -- the same brand reading
		# two different totals in two reports was the whole confusion
		{"label": _("Amount (incl. GST)"), "fieldname": "amount", "fieldtype": "Currency", "width": 170},
		# beside the amount it is netted out of, so the difference is plain
		{"label": _("Returns (incl. GST)"), "fieldname": "returns", "fieldtype": "Currency", "width": 150},
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
	if filters.get("exclude_returns"):
		conditions.append("si.is_return = 0")

	return frappe.db.sql(
		f"""
		select
			coalesce(nullif(item.brand, ''), '{_("Without Brand")}') as brand,
			-- base_amount, not base_net_amount: CA prices GST-inclusive, so
			-- this is what the line is actually billed at
			sum(sii.base_amount) as amount,
			-- shown on its own so a netted-off return is never a silent
			-- difference against somebody's spreadsheet
			sum(case when si.is_return = 1 then sii.base_amount else 0 end) as returns,
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
