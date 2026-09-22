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

PE_FIELD = "custom_post_dated_cheque"

PENDING = "Pending"
COLLECTED = "Collected"
RETURNED = "Returned"
BOUNCED = "Bounced"
CANCELLED = "Cancelled"


class PostDatedCheque(Document):
	def validate(self):
		self.set_sales_person()
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero."))
		if self.cheque_date and self.posting_date and getdate(self.cheque_date) < getdate(self.posting_date):
			frappe.msgprint(_("Cheque Date {0} is before the Posting Date; this cheque is not post dated.").format(self.cheque_date), indicator="orange", alert=True)
		self.validate_bank_account()
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

	def validate_bank_account(self):
		"""Keep the account tied to this customer, linking it if nobody owns it.

		A Bank Account made through the link field's own create dialog has no
		party, so it would never show up again. Using it here adopts it.
		"""
		if not self.bank_account:
			return
		account = frappe.db.get_value("Bank Account", self.bank_account, ["party_type", "party", "bank"], as_dict=True)
		if not account:
			frappe.throw(_("Bank Account {0} does not exist.").format(self.bank_account))
		if account.party and not (account.party_type == "Customer" and account.party == self.customer):
			frappe.throw(_("Bank Account {0} belongs to {1}.").format(self.bank_account, account.party))
		if not account.party:
			frappe.db.set_value("Bank Account", self.bank_account, {"party_type": "Customer", "party": self.customer})
		self.bank_name = account.bank


	def validate_duplicate(self):
		"""Cheque number is unique across all cheques, not just per customer.

		Cancelled cheques are ignored, so a number can be entered again after
		its entry is cancelled.
		"""
		existing = frappe.db.get_value(
			"Post Dated Cheque",
			{"cheque_no": self.cheque_no, "docstatus": ["<", 2], "name": ["!=", self.name]},
			["name", "customer_name"],
			as_dict=True,
		)
		if existing:
			frappe.throw(_("Cheque No {0} is already entered in {1} ({2}).").format(self.cheque_no, existing.name, existing.customer_name or ""))

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
def collect(cheque, bank_account=None, posting_date=None, mode_of_payment=None, reference_no=None, reference_date=None, remarks=None, references=None):
	"""One click: cheque cleared → Payment Entry against the customer."""
	doc = frappe.get_doc("Post Dated Cheque", cheque)
	doc.check_permission("write")
	doc.require_pending()

	mode_of_payment = mode_of_payment or "Cheque"
	bank_account = bank_account or mode_of_payment_account(mode_of_payment, doc.company)
	if not bank_account:
		frappe.throw(
			_("Mode of Payment {0} has no account for {1}. Set it in Mode of Payment.").format(mode_of_payment, doc.company)
		)

	posting_date = posting_date or doc.cheque_date or nowdate()
	savepoint = "pdc_collect"
	frappe.db.savepoint(savepoint)
	try:
		payment = frappe.new_doc("Payment Entry")
		payment.payment_type = "Receive"
		payment.company = doc.company
		payment.posting_date = posting_date
		payment.mode_of_payment = mode_of_payment
		payment.party_type = "Customer"
		payment.party = doc.customer
		payment.paid_from = frappe.get_cached_value("Company", doc.company, "default_receivable_account")
		payment.paid_to = bank_account
		payment.paid_amount = payment.received_amount = flt(doc.amount)
		payment.reference_no = reference_no or doc.cheque_no
		payment.reference_date = reference_date or doc.cheque_date
		payment.remarks = remarks or _("Post Dated Cheque {0}").format(doc.name)
		for row in _allocations(doc, references):
			payment.append("references", {
				"reference_doctype": "Sales Invoice",
				"reference_name": row["sales_invoice"],
				"allocated_amount": flt(row["allocated_amount"]),
			})
		payment.setup_party_account_field()
		payment.set_missing_values()
		payment.set_exchange_rate()
		payment.set(PE_FIELD, doc.name)
		payment.insert()
		payment.submit()
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		raise

	doc.db_set({"status": COLLECTED, "payment_entry": payment.name, "collected_on": posting_date})
	return {"payment_entry": payment.name, "status": COLLECTED}


def _allocations(doc, references):
	"""What the Payment Entry settles.

	The collect dialog may send invoice allocations; otherwise the cheque's
	own reference rows are used. Allocating nothing is fine — the payment
	then sits against the customer and can be reconciled later.
	"""
	rows = frappe.parse_json(references) if isinstance(references, str) else references
	if rows is None:
		return [
			{"sales_invoice": row.sales_invoice, "allocated_amount": flt(row.allocated_amount)}
			for row in doc.references
		]

	allocations = []
	total = 0
	for row in rows:
		invoice = row.get("sales_invoice")
		amount = flt(row.get("allocated_amount"))
		if not invoice or amount <= 0:
			continue
		details = frappe.db.get_value(
			"Sales Invoice", invoice, ["customer", "docstatus", "outstanding_amount"], as_dict=True
		)
		if not details or details.docstatus != 1:
			frappe.throw(_("Sales Invoice {0} is not submitted.").format(invoice))
		if details.customer != doc.customer:
			frappe.throw(_("Sales Invoice {0} belongs to {1}.").format(invoice, details.customer))
		if amount > flt(details.outstanding_amount) + 0.01:
			frappe.throw(
				_("Allocated {0} on {1} is more than its outstanding {2}.").format(
					amount, invoice, details.outstanding_amount
				)
			)
		total += amount
		allocations.append({"sales_invoice": invoice, "allocated_amount": amount})

	if flt(total, 2) > flt(doc.amount, 2):
		frappe.throw(_("Allocated {0} is more than the cheque amount {1}.").format(total, doc.amount))
	return allocations


@frappe.whitelist()
def outstanding_invoices(customer, company=None):
	"""The customer's open invoices, oldest first — shown when collecting."""
	filters = {"customer": customer, "docstatus": 1, "outstanding_amount": [">", 0]}
	if company:
		filters["company"] = company
	return frappe.get_all(
		"Sales Invoice",
		filters=filters,
		fields=["name as sales_invoice", "posting_date", "due_date", "grand_total", "outstanding_amount"],
		order_by="posting_date asc, name asc",
		limit=100,
	)


@frappe.whitelist()
def mark_bounced(cheque, reason=None):
	doc = frappe.get_doc("Post Dated Cheque", cheque)
	doc.check_permission("write")
	doc.require_pending()
	doc.db_set({"status": BOUNCED, "bounce_reason": reason})
	return {"status": BOUNCED}


REMINDER_DAYS = (7, 3, 1, 0)
EMAIL_DAYS = (1, 0)  # the creator is emailed the day before and on the day


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
		fields=["name", "cheque_no", "cheque_date", "customer", "customer_name", "amount", "sales_person", "bank_name", "company", "owner"],
	)
	sent = 0
	for cheque in cheques:
		days = date_diff(cheque.cheque_date, today)
		if days not in REMINDER_DAYS and days != -1:
			continue
		if days in EMAIL_DAYS:
			email_creator(cheque, days)
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


def email_creator(cheque, days):
	"""Mail whoever entered the cheque, the day before and on the day."""
	owner = cheque.get("owner")
	if not owner or owner == "Administrator" or not frappe.db.get_value("User", owner, "enabled"):
		return
	recipient = frappe.db.get_value("User", owner, "email") or owner
	when = _("today") if days == 0 else _("tomorrow")
	amount = frappe.format_value(cheque.amount, {"fieldtype": "Currency"})
	subject = _("Cheque due {0}: {1} — {2}").format(when, cheque.customer_name or cheque.customer, cheque.cheque_no)
	rows = [
		(_("Customer"), cheque.customer_name or cheque.customer),
		(_("Cheque No"), cheque.cheque_no),
		(_("Cheque Date"), frappe.format_value(cheque.cheque_date, {"fieldtype": "Date"})),
		(_("Amount"), amount),
		(_("Bank"), cheque.get("bank_name") or ""),
		(_("Sales Person"), cheque.get("sales_person") or ""),
	]
	body = "".join(
		f"<tr><td style='padding:4px 12px 4px 0;color:#6b7280'>{label}</td><td style='padding:4px 0'><b>{value}</b></td></tr>"
		for label, value in rows
		if value
	)
	frappe.sendmail(
		recipients=[recipient],
		subject=subject,
		message=_("Cheque {0} falls due {1}.").format(cheque.cheque_no, when)
		+ f"<table style='margin-top:10px'>{body}</table>"
		+ f"<p style='margin-top:12px'><a href='{frappe.utils.get_url_to_form('Post Dated Cheque', cheque.name)}'>{cheque.name}</a></p>",
		reference_doctype="Post Dated Cheque",
		reference_name=cheque.name,
		now=False,
	)


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


@frappe.whitelist()
def create_customer_bank_account(customer, bank, account_name=None, bank_account_no=None, ifsc=None, branch=None):
	"""Add the customer's bank account without leaving the cheque form.

	It is a normal Bank Account linked to the customer, so it shows on the
	customer and can be picked anywhere else. An account with the same
	number for that customer is reused instead of duplicated.
	"""
	frappe.has_permission("Post Dated Cheque", "write", throw=True)
	if not frappe.db.exists("Customer", customer):
		frappe.throw(_("Customer {0} does not exist.").format(customer))
	bank = (bank or "").strip()
	if not bank:
		frappe.throw(_("Enter the bank."))
	if not frappe.db.exists("Bank", bank):
		frappe.get_doc({"doctype": "Bank", "bank_name": bank}).insert(ignore_permissions=True)

	account_name = (account_name or frappe.db.get_value("Customer", customer, "customer_name") or customer).strip()
	bank_account_no = (bank_account_no or "").strip() or None

	existing = frappe.db.get_value(
		"Bank Account",
		{"party_type": "Customer", "party": customer, "bank": bank, "bank_account_no": bank_account_no},
		"name",
	)
	if existing:
		return {"name": existing, "bank": bank, "created": False}

	doc = frappe.get_doc({
		"doctype": "Bank Account",
		"account_name": account_name,
		"bank": bank,
		"party_type": "Customer",
		"party": customer,
		"is_company_account": 0,
		"bank_account_no": bank_account_no,
		"custom_ifsc": (ifsc or "").strip().upper() or None,
		"custom_branch": (branch or "").strip() or None,
	}).insert(ignore_permissions=True)
	return {"name": doc.name, "bank": bank, "created": True}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def customer_bank_accounts(doctype, txt, searchfield, start, page_len, filters):
	"""This customer's bank accounts, plus any that nobody owns yet."""
	customer = (filters or {}).get("customer")
	like = f"%{txt or ''}%"
	return frappe.db.sql(
		"""
		select name, concat_ws(' - ', bank, bank_account_no)
		from `tabBank Account`
		where disabled = 0 and ifnull(is_company_account, 0) = 0
			and (party = %(customer)s or ifnull(party, '') = '')
			and (name like %(like)s or ifnull(bank, '') like %(like)s or ifnull(account_name, '') like %(like)s)
		order by (party = %(customer)s) desc, name asc
		limit %(start)s, %(page_len)s
		""",
		{"customer": customer, "like": like, "start": start or 0, "page_len": page_len or 20},
	)


def allow_cheque_links_on_cancel(doc, method=None):
	"""Let a Payment Entry be cancelled although cheque records point at it.

	Frappe blocks cancelling a document that submitted documents link to.
	The cheque and its bounce entry are records *about* this payment, not
	downstream accounting, so they should not stand in the way — Cheque
	Bounce cancels the payment on purpose. It has to run in before_cancel:
	the check (check_no_back_links_exist) happens before on_cancel.
	"""
	doc.ignore_linked_doctypes = tuple(doc.get("ignore_linked_doctypes") or ()) + (
		"Post Dated Cheque",
		"Cheque Bounce",
	)


def on_cheque_bounce_submit(doc, method=None):
	"""A collected cheque that bounced: Cheque Bounce owns the accounting.

	It cancels the Payment Entry and books the bank charge; here we only
	mirror the outcome onto the cheque this Payment Entry came from.
	"""
	cheque = frappe.db.get_value("Post Dated Cheque", {"payment_entry": doc.payment_entry, "docstatus": 1}, "name")
	if not cheque:
		# the payment was just cancelled by this bounce, so the link is gone
		reset = frappe.flags.get("pdc_reset_by_payment_cancel") or []
		cheque = reset[0] if reset else None
	if not cheque:
		return
	frappe.db.set_value("Post Dated Cheque", cheque, {
		"status": BOUNCED,
		"bounce_reason": doc.get("bounce_reason"),
		"cheque_bounce": doc.name,
		"payment_entry": doc.payment_entry,
	})


def on_cheque_bounce_cancel(doc, method=None):
	"""Cancelling the bounce entry only unlinks it.

	The Payment Entry it cancelled is not restored by Cheque Bounce either,
	so the cheque stays Bounced until someone re-enters it.
	"""
	cheque = frappe.db.get_value("Post Dated Cheque", {"cheque_bounce": doc.name}, "name")
	if cheque:
		frappe.db.set_value("Post Dated Cheque", cheque, "cheque_bounce", None)


@frappe.whitelist()
def mode_of_payment_account(mode_of_payment, company):
	"""The account a mode of payment lands in for this company."""
	return frappe.db.get_value(
		"Mode of Payment Account", {"parent": mode_of_payment, "company": company}, "default_account"
	)


@frappe.whitelist()
def mark_returned(cheque, return_date=None, reason=None, bank_charge=0, bank_charges_account=None, remarks=None):
	"""The bank returned a cheque we had already banked.

	Both records are kept: the Payment Entry that brought the money in
	stays as it is, and a second one takes it back out, so the bank
	statement and the customer's ledger both read the way they happened.
	A bank charge, if any, is posted as its own Journal Entry.
	"""
	doc = frappe.get_doc("Post Dated Cheque", cheque)
	doc.check_permission("write")
	if doc.docstatus != 1 or doc.status != COLLECTED:
		frappe.throw(_("Only a Collected cheque can be returned; {0} is {1}.").format(doc.name, doc.status))
	if not doc.payment_entry or frappe.db.get_value("Payment Entry", doc.payment_entry, "docstatus") != 1:
		frappe.throw(_("The Payment Entry for this cheque is not submitted."))

	return_date = return_date or nowdate()
	original = frappe.get_doc("Payment Entry", doc.payment_entry)
	savepoint = "pdc_return"
	frappe.db.savepoint(savepoint)
	try:
		# the invoices this cheque had settled are owed again
		_unreconcile(original)
		reversal = frappe.new_doc("Payment Entry")
		reversal.payment_type = "Pay"
		reversal.company = doc.company
		reversal.posting_date = return_date
		reversal.mode_of_payment = original.mode_of_payment
		reversal.party_type = "Customer"
		reversal.party = doc.customer
		# money leaves the bank it came into, and the customer owes again
		reversal.paid_from = original.paid_to
		reversal.paid_to = original.paid_from
		reversal.paid_amount = reversal.received_amount = flt(doc.amount)
		reversal.reference_no = doc.cheque_no
		reversal.reference_date = return_date
		reversal.remarks = remarks or _("Cheque {0} returned by the bank").format(doc.cheque_no)
		reversal.setup_party_account_field()
		reversal.set_missing_values()
		reversal.set_exchange_rate()
		reversal.set(PE_FIELD, doc.name)
		reversal.insert()
		reversal.submit()

		# knock the return off the receipt so neither is left open
		_reconcile_against(doc, original.name, reversal.name)

		charge_entry = None
		if flt(bank_charge):
			charge_entry = _post_bank_charge(doc, original, return_date, flt(bank_charge), bank_charges_account)
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		raise

	doc.db_set({
		"status": RETURNED,
		"return_payment_entry": reversal.name,
		"returned_on": return_date,
		"bounce_reason": reason,
	})
	return {"status": RETURNED, "return_payment_entry": reversal.name, "bank_charge_entry": charge_entry}


def _unreconcile(payment):
	"""Detach the payment from the invoices it settled.

	Without this the invoice would still read as paid while the customer's
	balance went back up, so the receivable would be right in total but
	wrong invoice by invoice.
	"""
	if not payment.references:
		return

	from erpnext.accounts.doctype.unreconcile_payment.unreconcile_payment import (
		create_unreconcile_doc_for_selection,
	)

	selections = [
		{
			"company": payment.company,
			"voucher_type": payment.doctype,
			"voucher_no": payment.name,
			"against_voucher_type": row.reference_doctype,
			"against_voucher_no": row.reference_name,
		}
		for row in payment.references
	]
	create_unreconcile_doc_for_selection(selections=frappe.as_json(selections))


def _reconcile_against(doc, receipt, reversal):
	"""Settle the return against the receipt it reverses.

	Both sit on the customer otherwise — a credit for the money in and a
	debit for the money out — and the accounts team would have to match
	them by hand in Payment Reconciliation.
	"""
	try:
		reconciliation = frappe.new_doc("Payment Reconciliation")
		reconciliation.company = doc.company
		reconciliation.party_type = "Customer"
		reconciliation.party = doc.customer
		reconciliation.receivable_payable_account = frappe.get_cached_value(
			"Company", doc.company, "default_receivable_account"
		)
		reconciliation.get_unreconciled_entries()

		payment = next((row for row in reconciliation.payments if row.reference_name == receipt), None)
		invoice = next((row for row in reconciliation.invoices if row.invoice_number == reversal), None)
		if not (payment and invoice):
			return None

		reconciliation.append("allocation", {
			"reference_type": payment.reference_type,
			"reference_name": payment.reference_name,
			"invoice_type": invoice.invoice_type,
			"invoice_number": invoice.invoice_number,
			"allocated_amount": min(flt(payment.amount), flt(invoice.outstanding_amount)),
			"amount": payment.amount,
			"unreconciled_amount": payment.amount,
		})
		reconciliation.reconcile()
		return True
	except Exception:
		# the return itself must stand even if the match fails
		frappe.log_error(frappe.get_traceback(), "Post Dated Cheque: return not reconciled")
		return None


def _post_bank_charge(doc, original, return_date, amount, account=None):
	"""Dr Bank Charges, Cr the bank the cheque was banked into."""
	account = account or frappe.db.get_value(
		"Account", {"company": doc.company, "account_name": ["like", "%Bank Charges%"], "is_group": 0}, "name"
	)
	if not account:
		frappe.throw(_("Set the Bank Charges account to post a return charge."))

	entry = frappe.new_doc("Journal Entry")
	entry.voucher_type = "Bank Entry"
	entry.company = doc.company
	entry.posting_date = return_date
	entry.user_remark = _("Return charge for cheque {0} ({1})").format(doc.cheque_no, doc.name)
	# a Bank Entry needs a reference — the returned cheque is the reference
	entry.cheque_no = doc.cheque_no
	entry.cheque_date = return_date
	entry.append("accounts", {"account": account, "debit_in_account_currency": amount})
	entry.append("accounts", {"account": original.paid_to, "credit_in_account_currency": amount})
	entry.insert(ignore_permissions=True)
	entry.submit()
	return entry.name


def on_payment_entry_cancel(doc, method=None):
	"""Cancelling a payment must not drag the cheque down with it.

	Frappe would otherwise offer "Cancel All Documents" and cancel the
	cheque, losing the record. Instead the cheque goes back to the step
	before: a cancelled collection returns it to Pending, and a cancelled
	return puts it back to Collected. Clearing the link here also stops
	the cancel being blocked, because this runs before Frappe checks for
	back-links.
	"""
	reset = frappe.get_all(
		"Post Dated Cheque", filters={"payment_entry": doc.name, "docstatus": 1}, pluck="name"
	)
	# Cheque Bounce cancels the payment as part of its own flow and then
	# marks the cheque Bounced; leave it the names it can no longer find
	frappe.flags.pdc_reset_by_payment_cancel = reset
	for cheque in reset:
		frappe.db.set_value(
			"Post Dated Cheque", cheque, {"status": PENDING, "payment_entry": None, "collected_on": None}
		)
		frappe.get_doc("Post Dated Cheque", cheque).add_comment(
			"Comment", _("Back to Pending: Payment Entry {0} was cancelled.").format(doc.name)
		)

	for cheque in frappe.get_all(
		"Post Dated Cheque", filters={"return_payment_entry": doc.name, "docstatus": 1}, pluck="name"
	):
		frappe.db.set_value(
			"Post Dated Cheque",
			cheque,
			{"status": COLLECTED, "return_payment_entry": None, "returned_on": None, "bounce_reason": None},
		)
		frappe.get_doc("Post Dated Cheque", cheque).add_comment(
			"Comment", _("Back to Collected: the return entry {0} was cancelled.").format(doc.name)
		)


def ensure_payment_entry_field(*args, **kwargs):
	"""A link back from Payment Entry, so both entries show in Connections.

	The cheque links its collection entry, and the return entry links
	nothing — a dashboard can only follow one field per doctype, so the
	Payment Entries point at the cheque instead.
	"""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Payment Entry": [
				{
					"fieldname": PE_FIELD,
					"label": "Post Dated Cheque",
					"fieldtype": "Link",
					"options": "Post Dated Cheque",
					"insert_after": "reference_date",
					"read_only": 1,
					"no_copy": 1,
					"print_hide": 1,
					"module": "Chundakadan",
				}
			]
		},
		update=True,
	)
