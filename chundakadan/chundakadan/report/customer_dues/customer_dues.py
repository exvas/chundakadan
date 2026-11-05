# Copyright (c) 2026, Chundakadan and contributors
"""What each customer still owes, and whose job it is to collect it.

The Sales and Collection Summary answers "what moved in this period".
This answers a different question -- "what is outstanding right now" --
and the two must not be confused: that report's Balance is the period's
sales minus the period's receipts, which is not a debt. A customer who
bought nothing this month and owes five lakhs from March shows a Balance
of zero there and five lakhs here.

So there is no date range. A due is a due whenever it was billed.

Opening invoices count. They are money owed even though they were never
anybody's sale -- the Sales and Collection Summary leaves them out of
sales for exactly that reason, and leaving them out here would understate
every old customer's debt.

Returns carry a negative outstanding, so a credit note nets off against
what the customer owes.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

#: an invoice's own sales person is who sold it; where it has none -- every
#: opening invoice, for one -- the customer's current sales person is who
#: has to go and collect it. Selling is history; collecting is somebody's
#: job today.
SALES_PERSON_SQL = """coalesce(
	nullif(si.custom_sales_person, ''),
	(select st.sales_person from `tabSales Team` st
	  where st.parent = si.customer and st.parenttype = 'Customer'
	  order by st.idx limit 1)
)"""

#: the customer's territory, not the invoice's copy of it: the invoice
#: keeps whatever was on the customer the day it was raised, and the
#: territories were corrected on the customers afterwards
CUSTOMER_JOIN = "join `tabCustomer` cust on cust.name = si.customer"

OPEN_INVOICE = [
	"si.docstatus = 1",
	"si.company = %(company)s",
	"round(si.outstanding_amount, 2) <> 0",
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("company"):
		frappe.throw(_("Select a Company"))
	if filters.get("detail"):
		return get_detail_columns(), _detail(filters)
	return get_columns(), _summary(filters)


def get_columns():
	return [
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 110,
		},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 220},
		{
			"label": _("Territory"),
			"fieldname": "territory",
			"fieldtype": "Link",
			"options": "Territory",
			"width": 130,
		},
		{
			"label": _("Sales Person"),
			"fieldname": "sales_person",
			"fieldtype": "Link",
			"options": "Sales Person",
			"width": 160,
		},
		{"label": _("Invoices"), "fieldname": "invoices", "fieldtype": "Int", "width": 80},
		{"label": _("Outstanding"), "fieldname": "outstanding", "fieldtype": "Currency", "width": 140},
		{"label": _("Oldest Bill"), "fieldname": "oldest_date", "fieldtype": "Date", "width": 110},
		{"label": _("Days Overdue"), "fieldname": "days_overdue", "fieldtype": "Int", "width": 110},
	]


def get_detail_columns():
	return [
		{
			"label": _("Invoice"),
			"fieldname": "invoice",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 160,
		},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 100},
		{"label": _("Days Overdue"), "fieldname": "days_overdue", "fieldtype": "Int", "width": 110},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 110,
		},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
		{
			"label": _("Sales Person"),
			"fieldname": "sales_person",
			"fieldtype": "Link",
			"options": "Sales Person",
			"width": 150,
		},
		{"label": _("Invoice Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 130},
		{"label": _("Outstanding"), "fieldname": "outstanding", "fieldtype": "Currency", "width": 130},
	]


def _conditions(filters):
	"""Which invoices are still owed. Shared by the list and the totals, so
	a customer's rows always add up to the figure above them."""
	conditions = list(OPEN_INVOICE)
	if filters.get("customer"):
		conditions.append("si.customer = %(customer)s")
	if filters.get("territory"):
		conditions.append("cust.territory = %(territory)s")
	if filters.get("sales_person"):
		conditions.append(f"{SALES_PERSON_SQL} = %(sales_person)s")
	return conditions


def _days_overdue(due_date):
	if not due_date:
		return 0
	days = (getdate(today()) - getdate(due_date)).days
	return days if days > 0 else 0


def _summary(filters):
	"""One row per customer per collector.

	A customer whose debt sits partly with one executive and partly with
	another is two rows, because it is two people's work -- filter by sales
	person and it collapses to the one row that is theirs.
	"""
	rows = frappe.db.sql(
		f"""
		select
			si.customer,
			si.customer_name,
			cust.territory,
			{SALES_PERSON_SQL} as sales_person,
			count(si.name) as invoices,
			sum(si.outstanding_amount) as outstanding,
			min(si.posting_date) as oldest_date,
			min(si.due_date) as oldest_due
		from `tabSales Invoice` si
		{CUSTOMER_JOIN}
		where {" and ".join(_conditions(filters))}
		group by si.customer, si.customer_name, cust.territory, sales_person
		""",
		filters,
		as_dict=True,
	)
	for row in rows:
		row["days_overdue"] = _days_overdue(row.pop("oldest_due", None))
	rows.sort(key=lambda r: -flt(r.get("outstanding")))
	return rows


def _detail(filters):
	"""Every open invoice behind the figure, oldest first -- the order
	somebody chasing a payment works in."""
	rows = frappe.db.sql(
		f"""
		select
			si.name as invoice,
			si.posting_date,
			si.due_date,
			si.customer,
			si.customer_name,
			{SALES_PERSON_SQL} as sales_person,
			si.base_grand_total as grand_total,
			si.outstanding_amount as outstanding
		from `tabSales Invoice` si
		{CUSTOMER_JOIN}
		where {" and ".join(_conditions(filters))}
		order by si.due_date, si.posting_date, si.name
		""",
		filters,
		as_dict=True,
	)
	for row in rows:
		row["days_overdue"] = _days_overdue(row.get("due_date"))
	return rows
