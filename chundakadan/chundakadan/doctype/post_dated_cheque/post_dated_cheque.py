"""Post Dated Cheque — a cheque held until its date, tracked outside the books.

Nothing here touches the ledger. The cheque only becomes accounting when it
clears: `collect()` builds and submits a normal Payment Entry against the
customer and marks the cheque Collected.

Status: Draft → Pending (on submit) → Collected / Bounced, or Cancelled.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, flt, getdate, nowdate

PENDING = "Pending"
COLLECTED = "Collected"
BOUNCED = "Bounced"
CANCELLED = "Cancelled"


class PostDatedCheque(Document):
	def validate(self):
		self.set_sales_person()
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero."))
		if self.cheque_date and self.posting_date and getdate(self.cheque_date) < getdate(self.posting_date):
			frappe.msgprint(_("Cheque Date {0} is before the Posting Date; this cheque is not post dated.").format(self.cheque_date), indicator="orange", alert=True)
		self.validate_duplicate()
		self.validate_references()
		if self.docstatus == 0:
			self.status = "Draft"

	def set_sales_person(self):
		"""Mandatory, but filled in for the user wherever we can.

		A referenced invoice first, then the customer's latest submitted
		invoice (no customer here carries a Sales Team), then the team.
		"""
		if self.sales_person:
			return
		for row in self.references:
			person = frappe.db.get_value("Sales Invoice", row.sales_invoice, "custom_sales_person")
			if person:
				self.sales_person = person
				return
		if self.customer:
			latest = frappe.get_all(
				"Sales Invoice",
				filters={"customer": self.customer, "docstatus": 1, "custom_sales_person": ["is", "set"]},
				fields=["custom_sales_person"],
				order_by="posting_date desc, creation desc",
				limit=1,
			)
			if latest:
				self.sales_person = latest[0].custom_sales_person
				return
		self.sales_person = frappe.db.get_value("Sales Team", {"parent": self.customer, "parenttype": "Customer"}, "sales_person")

	def validate_duplicate(self):
		existing = frappe.db.exists(
			"Post Dated Cheque",
			{"cheque_no": self.cheque_no, "customer": self.customer, "docstatus": ["<", 2], "name": ["!=", self.name]},
		)
		if existing:
			frappe.throw(_("Cheque {0} for this customer is already entered in {1}.").format(self.cheque_no, existing))

	def validate_references(self):
		total = 0
		for row in self.references:
			invoice = frappe.db.get_value("Sales Invoice", row.sales_invoice, ["customer", "docstatus", "outstanding_amount"], as_dict=True)
			if not invoice or invoice.docstatus != 1:
				frappe.throw(_("Row #{0}: Sales Invoice {1} is not submitted.").format(row.idx, row.sales_invoice))
			if invoice.customer != self.customer:
				frappe.throw(_("Row #{0}: Sales Invoice {1} belongs to {2}.").format(row.idx, row.sales_invoice, invoice.customer))
			row.outstanding_amount = invoice.outstanding_amount
			if not flt(row.allocated_amount):
				row.allocated_amount = min(flt(invoice.outstanding_amount), flt(self.amount) - total)
			total += flt(row.allocated_amount)
		if self.references and flt(total, 2) > flt(self.amount, 2):
			frappe.throw(_("Allocated amount {0} is more than the cheque amount {1}.").format(total, self.amount))

	def on_submit(self):
		self.db_set("status", PENDING)

	def on_cancel(self):
		if self.payment_entry and frappe.db.get_value("Payment Entry", self.payment_entry, "docstatus") == 1:
			frappe.throw(_("Cancel Payment Entry {0} first.").format(self.payment_entry))
		self.db_set("status", CANCELLED)

	def require_pending(self):
		if self.docstatus != 1:
			frappe.throw(_("Submit the cheque first."))
		if self.status != PENDING:
			frappe.throw(_("Cheque {0} is {1}; only a Pending cheque can be updated.").format(self.name, self.status))


@frappe.whitelist()
def collect(cheque, bank_account, posting_date=None, mode_of_payment=None, reference_no=None, reference_date=None, remarks=None):
	"""One click: cheque cleared → Payment Entry against the customer."""
	doc = frappe.get_doc("Post Dated Cheque", cheque)
	doc.check_permission("write")
	doc.require_pending()

	posting_date = posting_date or doc.cheque_date or nowdate()
	savepoint = "pdc_collect"
	frappe.db.savepoint(savepoint)
	try:
		payment = frappe.new_doc("Payment Entry")
		payment.payment_type = "Receive"
		payment.company = doc.company
		payment.posting_date = posting_date
		payment.mode_of_payment = mode_of_payment or "Cheque"
		payment.party_type = "Customer"
		payment.party = doc.customer
		payment.paid_from = frappe.get_cached_value("Company", doc.company, "default_receivable_account")
		payment.paid_to = bank_account
		payment.paid_amount = payment.received_amount = flt(doc.amount)
		payment.reference_no = reference_no or doc.cheque_no
		payment.reference_date = reference_date or doc.cheque_date
		payment.remarks = remarks or _("Post Dated Cheque {0}").format(doc.name)
		for row in doc.references:
			payment.append("references", {
				"reference_doctype": "Sales Invoice",
				"reference_name": row.sales_invoice,
				"allocated_amount": flt(row.allocated_amount),
			})
		payment.setup_party_account_field()
		payment.set_missing_values()
		payment.set_exchange_rate()
		payment.insert()
		payment.submit()
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		raise

	doc.db_set({"status": COLLECTED, "payment_entry": payment.name, "collected_on": posting_date})
	return {"payment_entry": payment.name, "status": COLLECTED}


@frappe.whitelist()
def mark_bounced(cheque, reason=None):
	doc = frappe.get_doc("Post Dated Cheque", cheque)
	doc.check_permission("write")
	doc.require_pending()
	doc.db_set({"status": BOUNCED, "bounce_reason": reason})
	return {"status": BOUNCED}


REMINDER_DAYS = (7, 3, 1, 0)


def send_due_reminders():
	"""Daily: remind the sales person (and accounts) about cheques coming due.

	Runs 7, 3 and 1 days before the cheque date and on the day itself, plus
	once for anything already overdue and still Pending.
	"""
	from chundakadan.utils.push import send_to_users

	today = getdate(nowdate())
	cheques = frappe.get_all(
		"Post Dated Cheque",
		filters={"docstatus": 1, "status": PENDING},
		fields=["name", "cheque_no", "cheque_date", "customer_name", "amount", "sales_person", "company", "owner"],
	)
	sent = 0
	for cheque in cheques:
		days = date_diff(cheque.cheque_date, today)
		if days not in REMINDER_DAYS and days != -1:
			continue
		users = reminder_recipients(cheque)
		if not users:
			continue
		when = _("today") if days == 0 else (_("in {0} days").format(days) if days > 0 else _("yesterday; it is overdue"))
		send_to_users(
			list(users),
			_("Cheque due {0}").format(when),
			_("{0} — cheque {1} for {2}").format(cheque.customer_name, cheque.cheque_no, frappe.format_value(cheque.amount, {"fieldtype": "Currency"})),
			{"route": f"/app/post-dated-cheque/{cheque.name}", "doctype": "Post Dated Cheque", "name": cheque.name},
		)
		sent += 1
	return {"reminded": sent, "checked": len(cheques)}


def reminder_recipients(cheque):
	users = set()
	if cheque.get("sales_person"):
		employee = frappe.db.get_value("Sales Person", cheque.sales_person, "employee")
		user = frappe.db.get_value("Employee", employee, "user_id") if employee else None
		if user:
			users.add(user)
	for user in frappe.get_all("Has Role", filters={"role": "Accounts Manager", "parenttype": "User"}, pluck="parent"):
		if frappe.db.get_value("User", user, "enabled"):
			users.add(user)
	if cheque.get("owner") and frappe.db.get_value("User", cheque.owner, "enabled"):
		users.add(cheque.owner)
	users.discard("Administrator")
	return users
