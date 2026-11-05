# Copyright (c) 2026, Chundakadan and contributors
"""What was sold and what came back in, side by side.

Sales are submitted Sales Invoices (returns net off); collection is
submitted Payment Entries received from customers. Both are grouped the
same way, so a row reads "this brand / this executive sold X and collected
Y" over the same period.

Group By decides the rows: Brand, Sales Person, Customer, Day or Month.
Brand only exists on a sales line, so a collection cannot be attributed to
one -- grouped by brand the report shows sales alone and says so.
"""

import frappe
from frappe import _
from frappe.utils import getdate

GROUPS = {
	"Brand": {"label": _("Brand"), "fieldtype": "Link", "options": "Brand"},
	"Sales Person": {"label": _("Sales Person"), "fieldtype": "Link", "options": "Sales Person"},
	"Customer": {"label": _("Customer"), "fieldtype": "Link", "options": "Customer"},
	"Day": {"label": _("Date"), "fieldtype": "Date"},
	"Month": {"label": _("Month"), "fieldtype": "Data"},
}

#: collection cannot be split by brand — a payment is not against a line
SALES_ONLY = ("Brand",)

#: An opening invoice is a balance carried over from the old software on the
#: day the ERP went live, not something anyone sold. Counting it as sales puts
#: a salesman's whole inherited ledger into the month the books were opened —
#: for most of them more than everything they have actually sold since.
NOT_AN_OPENING = "ifnull(si.is_opening, '') <> 'Yes'"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not (filters.from_date and filters.to_date):
		frappe.throw(_("Select From Date and To Date"))
	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date"))
	group_by = filters.get("group_by") or "Sales Person"
	if group_by not in GROUPS:
		frappe.throw(_("Group By must be one of: {0}").format(", ".join(GROUPS)))
	filters.group_by = group_by

	if filters.get("collection_detail"):
		if group_by in SALES_ONLY:
			# don't silently hand back the summary as though the tick did
			# nothing -- say why there is no detail to show
			return (
				get_columns(filters),
				get_data(filters),
				_(
					"A payment is not received against an invoice line, so a collection "
					"cannot be attributed to a brand and there is no detail to list. "
					"Group by Sales Person, Customer, Day or Month to see one."
				),
			)
		return get_detail_columns(), _collection_detail(filters)

	return get_columns(filters), get_data(filters)


def get_columns(filters):
	group = GROUPS[filters.group_by]
	columns = [
		{
			"label": group["label"],
			"fieldname": "group_value",
			"fieldtype": group["fieldtype"],
			"options": group.get("options"),
			"width": 200,
		},
	]
	if filters.group_by == "Customer":
		# the codes are numbers here, so the column on its own says nothing
		columns.append(
			{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 220}
		)
	columns += [
		# say it on the label: this one carries the tax, and the Brand Wise
		# Sales Report does not, so the same brand reads differently there
		{"label": _("Sales (incl. GST)"), "fieldname": "sales", "fieldtype": "Currency", "width": 160},
		{"label": _("Invoices"), "fieldname": "invoices", "fieldtype": "Int", "width": 90},
		{"label": _("Qty Sold"), "fieldname": "qty", "fieldtype": "Float", "width": 110},
	]
	if filters.group_by not in SALES_ONLY:
		columns += [
			{"label": _("Collection"), "fieldname": "collection", "fieldtype": "Currency", "width": 140},
			{"label": _("Receipts"), "fieldname": "receipts", "fieldtype": "Int", "width": 90},
			{"label": _("Balance"), "fieldname": "balance", "fieldtype": "Currency", "width": 140},
		]
	return columns


def _month(value):
	return getdate(value).strftime("%b %Y")


def _sales(filters):
	"""Grouped sales, tax included. Returns are negative rows, so they net off.

	The figure has to tie to the Sales Register, which shows the invoice
	grand total -- so does this.

	Lines carry `base_amount` (tax included, because CA prices GST-inclusive)
	while `base_net_amount` strips the tax out; summing the net was what put
	this report below the register. Grand total also carries what sits on the
	invoice rather than on a line -- freight, for one -- so for a grouping that
	is a property of the invoice the sales figure is read from the invoice
	itself. Grouped by brand it cannot be: freight belongs to no brand, so
	those rows sum the lines and are tax-inclusive but carry no freight.
	"""
	conditions = [
		"si.docstatus = 1",
		NOT_AN_OPENING,
		"si.company = %(company)s",
		"si.posting_date between %(from_date)s and %(to_date)s",
	]
	if filters.get("sales_person"):
		conditions.append("si.custom_sales_person = %(sales_person)s")
	if filters.get("customer"):
		conditions.append("si.customer = %(customer)s")
	if filters.get("brand"):
		conditions.append("item.brand = %(brand)s")

	group_sql = {
		"Brand": "item.brand",
		"Sales Person": "si.custom_sales_person",
		"Customer": "si.customer",
		"Day": "si.posting_date",
		"Month": "date_format(si.posting_date, '%%Y-%%m')",
	}[filters.group_by]

	return frappe.db.sql(
		f"""
		select
			{group_sql} as group_value,
			sum(sii.base_amount) as sales,
			count(distinct si.name) as invoices,
			sum(sii.stock_qty) as qty,
			min(si.posting_date) as first_date
		from `tabSales Invoice Item` sii
		join `tabSales Invoice` si on si.name = sii.parent
		join `tabItem` item on item.name = sii.item_code
		where {" and ".join(conditions)}
		group by group_value
		""",
		filters,
		as_dict=True,
	)


def _invoice_group_sql(filters):
	return {
		"Sales Person": "si.custom_sales_person",
		"Customer": "si.customer",
		"Day": "si.posting_date",
		"Month": "date_format(si.posting_date, '%%Y-%%m')",
	}[filters.group_by]


def _invoice_totals(filters):
	"""Grand total per group, straight off the invoice.

	Only for a grouping the invoice itself carries, and only when no brand
	filter is on -- with one, an invoice's grand total would count lines of
	every other brand too.
	"""
	conditions = [
		"si.docstatus = 1",
		NOT_AN_OPENING,
		"si.company = %(company)s",
		"si.posting_date between %(from_date)s and %(to_date)s",
	]
	if filters.get("sales_person"):
		conditions.append("si.custom_sales_person = %(sales_person)s")
	if filters.get("customer"):
		conditions.append("si.customer = %(customer)s")

	rows = frappe.db.sql(
		f"""
		select {_invoice_group_sql(filters)} as group_value,
		       sum(si.base_grand_total) as sales
		from `tabSales Invoice` si
		where {" and ".join(conditions)}
		group by group_value
		""",
		filters,
		as_dict=True,
	)
	return {r.group_value: r.sales for r in rows}


def _collection_conditions(filters):
	"""Which receipts count. Shared, so the detail list cannot drift away
	from the figure it is there to prove."""
	conditions = [
		"pe.docstatus = 1",
		"pe.company = %(company)s",
		"pe.payment_type = 'Receive'",
		"pe.party_type = 'Customer'",
		"pe.posting_date between %(from_date)s and %(to_date)s",
	]
	if filters.get("sales_person"):
		conditions.append("pe.custom_sales_person = %(sales_person)s")
	if filters.get("customer"):
		conditions.append("pe.party = %(customer)s")
	return conditions


def _collection(filters):
	"""Grouped collection: money received from customers in the period."""
	if filters.group_by in SALES_ONLY:
		return []
	conditions = _collection_conditions(filters)

	group_sql = {
		"Sales Person": "pe.custom_sales_person",
		"Customer": "pe.party",
		"Day": "pe.posting_date",
		"Month": "date_format(pe.posting_date, '%%Y-%%m')",
	}[filters.group_by]

	return frappe.db.sql(
		f"""
		select
			{group_sql} as group_value,
			sum(pe.base_paid_amount) as collection,
			count(distinct pe.name) as receipts,
			min(pe.posting_date) as first_date
		from `tabPayment Entry` pe
		where {" and ".join(conditions)}
		group by group_value
		""",
		filters,
		as_dict=True,
	)


def get_detail_columns():
	"""One row per receipt. Sales Person and Customer are both named on
	every row whatever the grouping, because those are the two things
	somebody checking a collection is checking it against."""
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Sales Person"),
			"fieldname": "sales_person",
			"fieldtype": "Link",
			"options": "Sales Person",
			"width": 160,
		},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 120,
		},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 220},
		{
			"label": _("Payment Entry"),
			"fieldname": "payment_entry",
			"fieldtype": "Link",
			"options": "Payment Entry",
			"width": 150,
		},
		{
			"label": _("Mode of Payment"),
			"fieldname": "mode_of_payment",
			"fieldtype": "Link",
			"options": "Mode of Payment",
			"width": 130,
		},
		{"label": _("Reference No"), "fieldname": "reference_no", "fieldtype": "Data", "width": 130},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 130},
	]


def _collection_detail(filters):
	"""Every receipt behind the Collection figure, one row each.

	Same table, same conditions and the same amount column as _collection(),
	so the rows add up to the summary figure for the same filters -- which is
	the whole point of the list: it is what the summary is checked against.
	"""
	conditions = _collection_conditions(filters)

	order_by = {
		"Sales Person": "pe.custom_sales_person, pe.posting_date",
		"Customer": "pe.party, pe.posting_date",
		"Day": "pe.posting_date",
		"Month": "pe.posting_date",
	}[filters.group_by]

	return frappe.db.sql(
		f"""
		select
			pe.posting_date,
			pe.custom_sales_person as sales_person,
			pe.party as customer,
			pe.party_name as customer_name,
			pe.name as payment_entry,
			pe.mode_of_payment,
			pe.reference_no,
			pe.base_paid_amount as amount
		from `tabPayment Entry` pe
		where {" and ".join(conditions)}
		order by {order_by}, pe.name
		""",
		filters,
		as_dict=True,
	)


def get_data(filters):
	# the lines give the invoice count and the quantity; the sales figure
	# comes off the invoice itself wherever the grouping allows it, so the
	# total ties to the Sales Register
	totals = {}
	if filters.group_by not in SALES_ONLY and not filters.get("brand"):
		totals = _invoice_totals(filters)

	rows = {}
	for row in _sales(filters):
		key = row.group_value
		rows[key] = {
			"group_value": key,
			"sales": totals.get(key, row.sales) or 0,
			"invoices": row.invoices or 0,
			"qty": row.qty or 0,
			"collection": 0,
			"receipts": 0,
			"first_date": row.first_date,
		}
	for row in _collection(filters):
		key = row.group_value
		entry = rows.setdefault(
			key,
			{
				"group_value": key,
				"sales": 0,
				"invoices": 0,
				"qty": 0,
				"collection": 0,
				"receipts": 0,
				"first_date": row.first_date,
			},
		)
		entry["collection"] = row.collection or 0
		entry["receipts"] = row.receipts or 0

	if filters.group_by == "Customer":
		names = dict(
			frappe.get_all(
				"Customer",
				filters={"name": ["in", [k for k in rows if k]]},
				fields=["name", "customer_name"],
				as_list=True,
			)
		)
		for key, entry in rows.items():
			entry["customer_name"] = names.get(key)

	data = []
	for entry in rows.values():
		# sort on the raw value, never the label: "Sep 2026" sorts before
		# "Oct 2026" alphabetically, which puts the months in the wrong order
		entry["sort_key"] = str(entry["group_value"] or "")
		if not entry["group_value"]:
			entry["group_value"] = _("(not set)")
		elif filters.group_by == "Month":
			entry["group_value"] = _month(str(entry["group_value"]) + "-01")
		entry["balance"] = (entry["sales"] or 0) - (entry["collection"] or 0)
		entry.pop("first_date", None)
		data.append(entry)

	if filters.group_by in ("Day", "Month"):
		data.sort(key=lambda r: r["sort_key"])
	else:
		data.sort(key=lambda r: -(r["sales"] or 0))
	for entry in data:
		entry.pop("sort_key", None)
	return data
