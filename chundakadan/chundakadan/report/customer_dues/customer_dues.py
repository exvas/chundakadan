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

Money received and not yet put against any invoice counts too, as a
credit. Leaving it out was how the app came to show A K Trade Links
52,800 while their ledger read 42,800: a 10,000 receipt had been
submitted without being allocated, so no invoice's outstanding had
moved. Across the site that gap is 197 customers and 49 lakh -- an
executive sent to collect money the customer has already paid. The Due
column here is invoice outstanding minus that credit, which is what the
ledger says.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today


#: an invoice's own sales person is who sold it; where it has none -- every
#: opening invoice, for one -- the customer's current sales person is who
#: has to go and collect it. Selling is history; collecting is somebody's
#: job today.
def _sales_person_sql(table, party_field):
	return f"""coalesce(
		nullif({table}.custom_sales_person, ''),
		(select st.sales_person from `tabSales Team` st
		  where st.parent = {table}.{party_field} and st.parenttype = 'Customer'
		  order by st.idx limit 1)
	)"""


SALES_PERSON_SQL = _sales_person_sql("si", "customer")
RECEIPT_SALES_PERSON_SQL = _sales_person_sql("pe", "party")

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
		{"label": _("Outstanding"), "fieldname": "outstanding", "fieldtype": "Currency", "width": 130},
		# money received and not yet put against an invoice
		{"label": _("Advance"), "fieldname": "advance", "fieldtype": "Currency", "width": 120},
		{"label": _("Due"), "fieldname": "due", "fieldtype": "Currency", "width": 140},
		{"label": _("Oldest Bill"), "fieldname": "oldest_date", "fieldtype": "Date", "width": 110},
		{"label": _("Days Overdue"), "fieldname": "days_overdue", "fieldtype": "Int", "width": 110},
	]


def get_detail_columns():
	return [
		{"label": _("Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 110},
		{
			"label": _("Voucher"),
			"fieldname": "invoice",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
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
		{"label": _("Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 130},
		{"label": _("Outstanding"), "fieldname": "outstanding", "fieldtype": "Currency", "width": 130},
	]


def _receipt_conditions(filters):
	"""Receipts whose money has not been put against an invoice yet."""
	conditions = [
		"pe.docstatus = 1",
		"pe.company = %(company)s",
		"pe.payment_type = 'Receive'",
		"pe.party_type = 'Customer'",
		"round(pe.unallocated_amount, 2) > 0",
	]
	if filters.get("customer"):
		conditions.append("pe.party = %(customer)s")
	if filters.get("territory"):
		conditions.append("cust.territory = %(territory)s")
	if filters.get("sales_person"):
		conditions.append(f"{RECEIPT_SALES_PERSON_SQL} = %(sales_person)s")
	return conditions


def _advances(filters):
	"""Unallocated receipts, keyed the same way as the invoices so the two
	meet on the same row."""
	rows = frappe.db.sql(
		f"""
		select
			pe.party as customer,
			cust.customer_name,
			cust.territory,
			{RECEIPT_SALES_PERSON_SQL} as sales_person,
			sum(pe.unallocated_amount) as advance,
			count(pe.name) as receipts
		from `tabPayment Entry` pe
		join `tabCustomer` cust on cust.name = pe.party
		where {" and ".join(_receipt_conditions(filters))}
		group by pe.party, cust.customer_name, cust.territory, sales_person
		""",
		filters,
		as_dict=True,
	)
	return {(r["customer"], r["sales_person"]): r for r in rows}


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
	merged = {}
	for row in rows:
		row["days_overdue"] = _days_overdue(row.pop("oldest_due", None))
		row["advance"] = 0
		merged[(row["customer"], row["sales_person"])] = row

	for key, credit in _advances(filters).items():
		row = merged.get(key)
		if row:
			row["advance"] = credit["advance"]
			continue
		# paid and nothing open to put it against: the customer is in
		# credit, and leaving them out would stop the total tying to the
		# ledger
		merged[key] = {
			"customer": credit["customer"],
			"customer_name": credit["customer_name"],
			"territory": credit["territory"],
			"sales_person": credit["sales_person"],
			"invoices": 0,
			"outstanding": 0,
			"advance": credit["advance"],
			"oldest_date": None,
			"days_overdue": 0,
		}

	rows = list(merged.values())
	for row in rows:
		row["due"] = flt(row["outstanding"]) - flt(row["advance"])
	rows.sort(key=lambda r: -flt(r.get("due")))
	return rows


def _detail(filters):
	"""Every open invoice behind the figure, oldest first -- the order
	somebody chasing a payment works in."""
	rows = frappe.db.sql(
		f"""
		select
			'Sales Invoice' as voucher_type,
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

	# the credit belongs in the list too, or it would not add up to the Due
	# the customer's row shows
	receipts = frappe.db.sql(
		f"""
		select
			'Payment Entry' as voucher_type,
			pe.name as invoice,
			pe.posting_date,
			pe.party as customer,
			cust.customer_name,
			{RECEIPT_SALES_PERSON_SQL} as sales_person,
			pe.base_paid_amount as grand_total,
			-pe.unallocated_amount as outstanding
		from `tabPayment Entry` pe
		join `tabCustomer` cust on cust.name = pe.party
		where {" and ".join(_receipt_conditions(filters))}
		order by pe.posting_date, pe.name
		""",
		filters,
		as_dict=True,
	)
	for row in receipts:
		row["due_date"] = None
		row["days_overdue"] = 0
	return rows + receipts
