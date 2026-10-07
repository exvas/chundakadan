# Copyright (c) 2026, Chundakadan and contributors
"""The sales register the office files GST from.

Laid out column for column like the sheet the old software produced, so
the two can be read side by side: SlNo, Date, Voucher No, Party Name,
City, State, State Code, GST No, HSN, Item group, Amount, the three
rates, the three tax amounts, CESS, Total, Qty, Unit, Discount.

A row is one invoice's lines of one HSN of one brand, which is how the
old report cut it. Most invoices are a single row; a few carry two or
three HSNs and split accordingly, and the rows of an invoice still add
up to its taxable value and its tax.

"Amount" is the taxable value -- what GST is charged on -- so
Amount + CGST + SGST + IGST + CESS = Total. That is the register's
convention and it is not the same as the Sales Invoice grand total,
which also carries anything charged on the invoice rather than on a
line, freight for one.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

COMPANY = "Chundakadan Agencies"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not (filters.from_date and filters.to_date):
		frappe.throw(_("Select From Date and To Date"))
	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date"))
	if not filters.company:
		filters.company = COMPANY
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("SlNo"), "fieldname": "sl_no", "fieldtype": "Data", "width": 60},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 95},
		{"label": _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Link",
		 "options": "Sales Invoice", "width": 150},
		{"label": _("Party Name"), "fieldname": "party_name", "fieldtype": "Data", "width": 220},
		{"label": _("City"), "fieldname": "city", "fieldtype": "Data", "width": 120},
		{"label": _("State"), "fieldname": "state", "fieldtype": "Data", "width": 110},
		{"label": _("State Code"), "fieldname": "state_code", "fieldtype": "Data", "width": 80},
		{"label": _("GST No"), "fieldname": "gst_no", "fieldtype": "Data", "width": 160},
		{"label": _("HSN"), "fieldname": "hsn", "fieldtype": "Data", "width": 100},
		{"label": _("Item group"), "fieldname": "item_group", "fieldtype": "Data", "width": 140},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		# the rates are labels, not money: as Data they stay out of the total row
		{"label": _("SGST%"), "fieldname": "sgst_rate", "fieldtype": "Data", "width": 70},
		{"label": _("CGST%"), "fieldname": "cgst_rate", "fieldtype": "Data", "width": 70},
		{"label": _("IGST%"), "fieldname": "igst_rate", "fieldtype": "Data", "width": 70},
		{"label": _("CGST"), "fieldname": "cgst", "fieldtype": "Currency", "width": 110},
		{"label": _("SGST"), "fieldname": "sgst", "fieldtype": "Currency", "width": 110},
		{"label": _("IGSTA"), "fieldname": "igst", "fieldtype": "Currency", "width": 110},
		{"label": _("CESS"), "fieldname": "cess", "fieldtype": "Currency", "width": 90},
		{"label": _("Total"), "fieldname": "total", "fieldtype": "Currency", "width": 130},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{"label": _("Unit"), "fieldname": "unit", "fieldtype": "Data", "width": 70},
		{"label": _("Discount"), "fieldname": "discount", "fieldtype": "Currency", "width": 100},
	]


def _rate(value):
	"""9.0 reads as 9, and a rate that is not charged is left blank."""
	value = flt(value)
	if not value:
		return None
	return str(int(value)) if value == int(value) else str(value)


def get_data(filters):
	conditions = [
		"si.docstatus = 1",
		"si.company = %(company)s",
		"si.posting_date between %(from_date)s and %(to_date)s",
	]
	if filters.get("customer"):
		conditions.append("si.customer = %(customer)s")
	if filters.get("brand"):
		conditions.append("item.brand = %(brand)s")

	rows = frappe.db.sql(
		f"""
		select
			si.name as voucher_no,
			si.posting_date as date,
			si.customer_name as party_name,
			si.billing_address_gstin as gst_no,
			si.place_of_supply as place_of_supply,
			addr.city as city,
			addr.state as state,
			sii.gst_hsn_code as hsn,
			item.brand as item_group,
			sum(sii.base_net_amount) as amount,
			max(sii.sgst_rate) as sgst_rate,
			max(sii.cgst_rate) as cgst_rate,
			max(sii.igst_rate) as igst_rate,
			sum(sii.cgst_amount) as cgst,
			sum(sii.sgst_amount) as sgst,
			sum(sii.igst_amount) as igst,
			sum(ifnull(sii.cess_amount, 0) + ifnull(sii.cess_non_advol_amount, 0)) as cess,
			sum(sii.qty) as qty,
			max(sii.uom) as unit,
			sum(ifnull(sii.discount_amount, 0) * sii.qty) as discount
		from `tabSales Invoice Item` sii
		join `tabSales Invoice` si on si.name = sii.parent
		join `tabItem` item on item.name = sii.item_code
		left join `tabAddress` addr on addr.name = si.customer_address
		where {" and ".join(conditions)}
		group by si.name, sii.gst_hsn_code, item.brand
		order by si.posting_date, si.name, sii.gst_hsn_code
		""",
		filters,
		as_dict=True,
	)

	data = []
	for i, row in enumerate(rows, start=1):
		row.sl_no = str(i)
		row.state_code = _state_code(row)
		row.total = (
			flt(row.amount) + flt(row.cgst) + flt(row.sgst) + flt(row.igst) + flt(row.cess)
		)
		for field in ("sgst_rate", "cgst_rate", "igst_rate"):
			row[field] = _rate(row.get(field))
		row.pop("place_of_supply", None)
		data.append(row)
	return data


def _state_code(row):
	"""The GST state number: off the place of supply, else off the GSTIN."""
	place = row.get("place_of_supply") or ""
	if "-" in place and place.split("-")[0].strip().isdigit():
		return place.split("-")[0].strip()
	gstin = (row.get("gst_no") or "").strip()
	if len(gstin) >= 2 and gstin[:2].isdigit():
		return gstin[:2]
	return None
