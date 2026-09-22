"""Customer Follow Up — a logged chase for money the customer owes.

Each entry records what happened (called, promised, disputed, paid) and
when to chase next. Saving one opens a task on that date and closes the
previous open chase for the same customer, so a customer has exactly one
chase running at a time. Nothing here touches the ledger.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate

OPEN = "Open"
CLOSED = "Closed"
PAID = "Paid"


class CustomerFollowUp(Document):
	def validate(self):
		if not self.follow_up_date:
			self.follow_up_date = nowdate()
		if self.outcome == PAID:
			self.next_follow_up_date = None
			self.status = CLOSED
		elif not self.next_follow_up_date:
			frappe.throw(_("Set the next follow-up date, or mark the outcome as Paid."))
		elif getdate(self.next_follow_up_date) < getdate(self.follow_up_date):
			frappe.throw(_("Next follow-up cannot be before the follow-up date."))
		if self.outcome != "Promised to Pay":
			self.promised_amount = 0
		if not self.outstanding_amount:
			self.outstanding_amount = customer_outstanding(self.customer, self.company)
		if not self.sales_person:
			self.sales_person = _sales_person_for(self.customer)

	def after_insert(self):
		self.close_previous_chases()
		self.create_task()

	def close_previous_chases(self):
		"""One running chase per customer: the new entry replaces the old."""
		previous = frappe.get_all(
			"Customer Follow Up",
			filters={"customer": self.customer, "company": self.company, "status": OPEN, "name": ["!=", self.name]},
			pluck="name",
		)
		for name in previous:
			doc = frappe.get_doc("Customer Follow Up", name)
			doc.db_set("status", CLOSED)
			doc.close_task()

	def create_task(self):
		if self.status == CLOSED or not self.next_follow_up_date:
			return
		amount = frappe.format_value(self.outstanding_amount, {"fieldtype": "Currency"})
		todo = frappe.get_doc({
			"doctype": "ToDo",
			"description": _("Follow up · {0} ({1})").format(self.customer_name or self.customer, amount),
			"reference_type": self.doctype,
			"reference_name": self.name,
			"date": self.next_follow_up_date,
			"allocated_to": self.owner,
			"priority": "Medium",
		}).insert(ignore_permissions=True)
		self.db_set("todo", todo.name)

	def close_task(self):
		if self.todo and frappe.db.get_value("ToDo", self.todo, "status") == "Open":
			frappe.db.set_value("ToDo", self.todo, "status", "Closed")

	def on_trash(self):
		if self.todo and frappe.db.exists("ToDo", self.todo):
			frappe.delete_doc("ToDo", self.todo, ignore_permissions=True, force=True)


def _sales_person_for(customer):
	person = frappe.db.get_value("Sales Team", {"parent": customer, "parenttype": "Customer"}, "sales_person")
	if person:
		return person
	latest = frappe.get_all(
		"Sales Invoice",
		filters={"customer": customer, "docstatus": 1, "custom_sales_person": ["is", "set"]},
		fields=["custom_sales_person"],
		order_by="posting_date desc, creation desc",
		limit=1,
	)
	return latest[0].custom_sales_person if latest else None


@frappe.whitelist()
def customer_outstanding(customer, company=None):
	"""What the customer owes right now, from submitted invoices."""
	filters = {"customer": customer, "docstatus": 1, "outstanding_amount": [">", 0]}
	if company:
		filters["company"] = company
	rows = frappe.get_all("Sales Invoice", filters=filters, fields=["sum(outstanding_amount) as total"])
	return flt(rows[0].total) if rows else 0.0


@frappe.whitelist()
def chase_history(customer, company=None, limit=10):
	"""Recent chases for this customer, newest first — shown on the form."""
	filters = {"customer": customer}
	if company:
		filters["company"] = company
	return frappe.get_all(
		"Customer Follow Up",
		filters=filters,
		fields=["name", "follow_up_date", "outcome", "status", "outstanding_amount", "promised_amount", "remarks", "next_follow_up_date"],
		order_by="follow_up_date desc, creation desc",
		limit=int(limit),
	)
