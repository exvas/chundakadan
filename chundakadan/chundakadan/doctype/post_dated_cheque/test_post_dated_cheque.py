import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate

from unittest.mock import patch

from chundakadan.chundakadan.doctype.post_dated_cheque.post_dated_cheque import (
	collect,
	create_customer_bank_account,
	customer_bank_accounts,
	mark_bounced,
	mode_of_payment_account,
	outstanding_invoices,
	reminder_recipients,
	send_due_reminders,
)
from chundakadan.chundakadan.report.post_dated_cheque_report.post_dated_cheque_report import execute

COMPANY = "Chundakadan Agencies"


def ensure_doctypes():
	"""The dev copy has no migrate run; import the doctype files as needed."""
	import os

	from frappe.modules.import_file import import_file_by_path

	base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	for name in ("post_dated_cheque_reference", "post_dated_cheque"):
		import_file_by_path(os.path.join(base, name, f"{name}.json"), force=True)
	report = os.path.join(os.path.dirname(base), "report", "post_dated_cheque_report", "post_dated_cheque_report.json")
	import_file_by_path(report, force=True)


class TestPostDatedCheque(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		ensure_doctypes()
		self.invoice = frappe.get_all(
			"Sales Invoice",
			filters={"docstatus": 1, "is_return": 0, "company": COMPANY, "outstanding_amount": [">", 0]},
			fields=["name", "customer", "outstanding_amount"],
			order_by="posting_date desc",
			limit=1,
		)
		if not self.invoice:
			self.skipTest("no outstanding Sales Invoice on this site")
		self.invoice = self.invoice[0]
		self.bank = frappe.db.get_value("Account", {"company": COMPANY, "account_type": "Bank", "is_group": 0}, "name")
		self.bank_account = create_customer_bank_account(self.invoice.customer, "Test Bank", bank_account_no="111000")["name"]

	def tearDown(self):
		frappe.db.rollback()

	def _cheque(self, submit=True, amount=None, **values):
		doc = frappe.get_doc({
			"doctype": "Post Dated Cheque",
			"company": COMPANY,
			"customer": self.invoice.customer,
			"posting_date": nowdate(),
			"cheque_no": frappe.generate_hash(length=8),
			"cheque_date": add_days(nowdate(), 30),
			"amount": amount or flt(self.invoice.outstanding_amount),
			"bank_account": self.bank_account,
			**values,
		})
		doc.insert()
		if submit:
			doc.submit()
			doc.reload()
		return doc

	def _gl_count(self):
		return frappe.db.count("GL Entry")

	def test_entry_does_not_touch_the_ledger(self):
		before_gl, before_outstanding = self._gl_count(), frappe.db.get_value("Sales Invoice", self.invoice.name, "outstanding_amount")
		doc = self._cheque()
		self.assertEqual(doc.status, "Pending")
		self.assertEqual(self._gl_count(), before_gl)
		self.assertEqual(frappe.db.get_value("Sales Invoice", self.invoice.name, "outstanding_amount"), before_outstanding)
		self.assertFalse(frappe.db.exists("Payment Entry", {"reference_no": doc.cheque_no}))

	def test_reference_allocation_defaults_and_validates(self):
		doc = self._cheque(submit=False, references=[{"sales_invoice": self.invoice.name}])
		self.assertEqual(flt(doc.references[0].outstanding_amount), flt(self.invoice.outstanding_amount))
		self.assertTrue(flt(doc.references[0].allocated_amount) > 0)
		doc.references[0].allocated_amount = flt(doc.amount) + 100
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_duplicate_cheque_blocked(self):
		doc = self._cheque()
		with self.assertRaises(frappe.ValidationError):
			self._cheque(cheque_no=doc.cheque_no)

	def test_duplicate_blocked_across_customers_too(self):
		other = frappe.db.get_value("Customer", {"name": ["!=", self.invoice.customer], "disabled": 0}, "name")
		if not other:
			self.skipTest("only one customer")
		doc = self._cheque()
		with self.assertRaises(frappe.ValidationError):
			self._cheque(cheque_no=doc.cheque_no, customer=other, sales_person=doc.sales_person)

	def test_number_reusable_after_cancel(self):
		doc = self._cheque()
		doc.cancel()
		again = self._cheque(cheque_no=doc.cheque_no)
		self.assertEqual(again.cheque_no, doc.cheque_no)

	def test_collect_creates_payment_entry_and_settles_invoice(self):
		outstanding_before = flt(frappe.db.get_value("Sales Invoice", self.invoice.name, "outstanding_amount"))
		doc = self._cheque(references=[{"sales_invoice": self.invoice.name}])
		result = collect(doc.name, bank_account=self.bank, posting_date=nowdate())
		payment = frappe.get_doc("Payment Entry", result["payment_entry"])
		self.assertEqual(payment.docstatus, 1)
		self.assertEqual((payment.party, payment.payment_type, payment.paid_to), (doc.customer, "Receive", self.bank))
		self.assertEqual(flt(payment.paid_amount), flt(doc.amount))
		self.assertEqual(payment.reference_no, doc.cheque_no)
		doc.reload()
		self.assertEqual((doc.status, doc.payment_entry), ("Collected", payment.name))
		after = flt(frappe.db.get_value("Sales Invoice", self.invoice.name, "outstanding_amount"))
		self.assertAlmostEqual(after, outstanding_before - flt(doc.references[0].allocated_amount), places=2)

	def test_collect_twice_is_blocked(self):
		doc = self._cheque()
		collect(doc.name, bank_account=self.bank)
		with self.assertRaises(frappe.ValidationError):
			collect(doc.name, bank_account=self.bank)

	def test_collect_rolls_back_on_failure(self):
		doc = self._cheque()
		before = frappe.db.count("Payment Entry")
		with self.assertRaises(Exception):
			collect(doc.name, bank_account="Nope - XX")
		doc.reload()
		self.assertEqual(doc.status, "Pending")
		self.assertEqual(frappe.db.count("Payment Entry"), before)

	def test_mark_bounced(self):
		doc = self._cheque()
		mark_bounced(doc.name, reason="Insufficient funds")
		doc.reload()
		self.assertEqual((doc.status, doc.bounce_reason), ("Bounced", "Insufficient funds"))
		with self.assertRaises(frappe.ValidationError):
			collect(doc.name, bank_account=self.bank)

	def test_cancel_sets_status(self):
		doc = self._cheque()
		doc.cancel()
		doc.reload()
		self.assertEqual(doc.status, "Cancelled")

	def test_cancel_blocked_while_payment_entry_live(self):
		doc = self._cheque()
		collect(doc.name, bank_account=self.bank)
		doc.reload()
		with self.assertRaises(frappe.ValidationError):
			doc.cancel()

	def test_report_columns_and_rows(self):
		doc = self._cheque(references=[{"sales_invoice": self.invoice.name}])
		columns, data = execute({"company": COMPANY, "status": "Pending"})
		names = [c["fieldname"] for c in columns]
		for field in ("cheque_date", "customer_name", "amount", "posting_date", "status"):
			self.assertIn(field, names)
		row = next(r for r in data if r["name"] == doc.name)
		self.assertEqual((row["cheque_no"], flt(row["amount"]), row["status"]), (doc.cheque_no, flt(doc.amount), "Pending"))
		self.assertEqual(row["invoices"], self.invoice.name)
		self.assertEqual(row["days_to_due"], 30)

	def test_report_status_filter(self):
		doc = self._cheque()
		mark_bounced(doc.name, reason="x")
		_, pending = execute({"company": COMPANY, "status": "Pending"})
		self.assertNotIn(doc.name, [r["name"] for r in pending])
		_, bounced = execute({"company": COMPANY, "status": "Bounced"})
		self.assertIn(doc.name, [r["name"] for r in bounced])

	# ---- sales person + reminders -------------------------------------

	def test_sales_person_comes_from_the_invoice(self):
		person = frappe.db.get_value("Sales Invoice", self.invoice.name, "custom_sales_person")
		if not person:
			self.skipTest("invoice has no sales person")
		doc = self._cheque(references=[{"sales_invoice": self.invoice.name}])
		self.assertEqual(doc.sales_person, person)

	def test_sales_person_falls_back_to_the_customers_latest_invoice(self):
		latest = frappe.get_all(
			"Sales Invoice",
			filters={"customer": self.invoice.customer, "docstatus": 1, "custom_sales_person": ["is", "set"]},
			fields=["custom_sales_person"],
			order_by="posting_date desc, creation desc",
			limit=1,
		)
		if not latest:
			self.skipTest("customer has no invoice with a sales person")
		doc = self._cheque()
		self.assertEqual(doc.sales_person, latest[0].custom_sales_person)

	def test_sales_person_is_mandatory(self):
		self.assertEqual(frappe.get_meta("Post Dated Cheque").get_field("sales_person").reqd, 1)
		invoiced = frappe.get_all("Sales Invoice", filters={"docstatus": 1}, pluck="customer") or [""]
		customer = frappe.db.get_value("Customer", {"name": ["not in", invoiced]}, "name")
		if not customer:
			self.skipTest("every customer has invoices")
		account = create_customer_bank_account(customer, "Test Bank 5", bank_account_no="5555")["name"]
		with self.assertRaises(frappe.exceptions.MandatoryError):
			self._cheque(submit=False, customer=customer, bank_account=account)

	def test_sales_person_kept_when_set(self):
		person = frappe.db.get_value("Sales Person", {"enabled": 1}, "name")
		doc = self._cheque(sales_person=person, references=[{"sales_invoice": self.invoice.name}])
		self.assertEqual(doc.sales_person, person)

	def _reminder_run(self, cheque_date):
		# the caller rolls back between runs, so the bank account is gone too
		self.bank_account = create_customer_bank_account(self.invoice.customer, "Test Bank", bank_account_no="111000")["name"]
		self._cheque(cheque_date=cheque_date)
		with patch("chundakadan.utils.push.send_to_users") as push:
			result = send_due_reminders()
		return result, push

	def test_reminder_fires_on_the_due_days_only(self):
		for days, expected in ((3, True), (1, True), (0, True), (5, False)):
			frappe.db.rollback()
			ensure_doctypes()
			result, push = self._reminder_run(add_days(nowdate(), days))
			self.assertEqual(push.called, expected, f"{days} days")

	def test_reminder_skips_collected_cheques(self):
		doc = self._cheque(cheque_date=nowdate())
		collect(doc.name, bank_account=self.bank)
		with patch("chundakadan.utils.push.send_to_users") as push:
			send_due_reminders()
		names = [call.args[3].get("name") for call in push.call_args_list if len(call.args) > 3]
		self.assertNotIn(doc.name, names)

	def test_reminder_recipients_include_the_sales_person_user(self):
		person = frappe.db.get_value("Sales Person", {"enabled": 1, "employee": ["is", "set"]}, "name")
		if not person:
			self.skipTest("no sales person linked to an employee")
		employee = frappe.db.get_value("Sales Person", person, "employee")
		user = frappe.db.get_value("Employee", employee, "user_id")
		if not user:
			self.skipTest("sales person has no user")
		doc = self._cheque(sales_person=person)
		self.assertIn(user, reminder_recipients(frappe._dict(doc.as_dict())))

	# ---- customer bank account ----------------------------------------

	def test_bank_account_is_optional(self):
		# the PDC import from the customer's own list has no bank details
		self.assertFalse(frappe.get_meta("Post Dated Cheque").get_field("bank_account").reqd)
		doc = self._cheque(bank_account=None)
		self.assertEqual(doc.status, "Pending")
		self.assertFalse(doc.bank_name)

	def test_create_customer_bank_account_links_the_customer(self):
		result = create_customer_bank_account(self.invoice.customer, "Test Bank 2", account_name="Test A/C", bank_account_no="222333", ifsc="sbin0001234", branch="Calicut")
		account = frappe.get_doc("Bank Account", result["name"])
		self.assertTrue(result["created"])
		self.assertEqual((account.party_type, account.party, account.bank), ("Customer", self.invoice.customer, "Test Bank 2"))
		self.assertEqual((account.bank_account_no, account.custom_ifsc, account.custom_branch), ("222333", "SBIN0001234", "Calicut"))
		self.assertEqual(account.is_company_account, 0)
		self.assertTrue(frappe.db.exists("Bank", "Test Bank 2"))

	def test_create_customer_bank_account_reuses_the_same_account(self):
		first = create_customer_bank_account(self.invoice.customer, "Test Bank 3", bank_account_no="9999")
		again = create_customer_bank_account(self.invoice.customer, "Test Bank 3", bank_account_no="9999")
		self.assertEqual(first["name"], again["name"])
		self.assertFalse(again["created"])

	def test_bank_account_of_another_customer_blocked(self):
		other = frappe.db.get_value("Customer", {"name": ["!=", self.invoice.customer], "disabled": 0}, "name")
		if not other:
			self.skipTest("only one customer")
		theirs = create_customer_bank_account(other, "Test Bank 4", bank_account_no="4444")["name"]
		with self.assertRaises(frappe.ValidationError):
			self._cheque(submit=False, bank_account=theirs)

	def test_bank_name_fetched_from_the_account(self):
		doc = self._cheque()
		self.assertEqual(doc.bank_name, "Test Bank")

	def test_invoice_references_are_optional(self):
		self.assertFalse(frappe.get_meta("Post Dated Cheque").get_field("references").reqd)
		doc = self._cheque()
		self.assertEqual(doc.references, [])
		self.assertEqual(doc.status, "Pending")

	def test_permissions_are_accounts_roles(self):
		roles = {p.role for p in frappe.get_meta("Post Dated Cheque").permissions}
		self.assertTrue({"Accounts User", "Accounts Manager", "Sales User"}.issubset(roles))
		sales = next(p for p in frappe.get_meta("Post Dated Cheque").permissions if p.role == "Sales User")
		self.assertEqual((sales.read, sales.write, sales.create, sales.submit), (1, 0, 0, 0))
		report_roles = {r.role for r in frappe.get_doc("Report", "Post Dated Cheque Report").roles}
		self.assertTrue({"Accounts User", "Accounts Manager", "Sales User"}.issubset(report_roles))

	def _orphan_account(self, name="Orphan Bank"):
		if not frappe.db.exists("Bank", name):
			frappe.get_doc({"doctype": "Bank", "bank_name": name}).insert()
		return frappe.get_doc({"doctype": "Bank Account", "account_name": f"Orphan {frappe.generate_hash(length=5)}", "bank": name}).insert().name

	def test_unowned_bank_account_is_adopted(self):
		# made through the link field's own create dialog, so it has no party
		account = self._orphan_account()
		self.assertFalse(frappe.db.get_value("Bank Account", account, "party"))
		doc = self._cheque(bank_account=account)
		self.assertEqual(
			frappe.db.get_value("Bank Account", account, ["party_type", "party"], as_dict=True),
			frappe._dict({"party_type": "Customer", "party": self.invoice.customer}),
		)
		self.assertEqual(doc.bank_name, "Orphan Bank")

	def test_query_lists_own_and_unowned_accounts(self):
		mine = self.bank_account
		orphan = self._orphan_account()
		other = frappe.db.get_value("Customer", {"name": ["!=", self.invoice.customer], "disabled": 0}, "name")
		theirs = create_customer_bank_account(other, "Someone Elses Bank", bank_account_no="7777")["name"] if other else None
		names = [row[0] for row in customer_bank_accounts("Bank Account", "", "name", 0, 50, {"customer": self.invoice.customer})]
		self.assertIn(mine, names)
		self.assertIn(orphan, names)
		if theirs:
			self.assertNotIn(theirs, names)

	# ---- collected cheque that bounced --------------------------------

	def _cheque_bounce_doc(self, pdc, charge=0):
		company = COMPANY
		return frappe.get_doc({
			"doctype": "Cheque Bounce",
			"payment_entry": pdc.payment_entry,
			"customer": pdc.customer,
			"bounce_date": nowdate(),
			"cheque_no": pdc.cheque_no,
			"cheque_date": pdc.cheque_date,
			"original_amount": pdc.amount,
			"mode_of_payment": "Cheque",
			"bounce_reason": "Insufficient Funds",
			"bounce_charge_amount": charge,
			"charge_to_customer": 0,
			"bank_account": self.bank,
			"bank_charges_account": frappe.db.get_value("Account", {"company": company, "account_name": ["like", "%Bank Charges%"], "is_group": 0}, "name") or self.bank,
		})

	def test_cheque_bounce_marks_the_cheque_bounced(self):
		if not frappe.db.exists("DocType", "Cheque Bounce"):
			self.skipTest("field_sales Cheque Bounce not installed")
		doc = self._cheque()
		collect(doc.name, bank_account=self.bank)
		doc.reload()
		self.assertEqual(doc.status, "Collected")
		bounce = self._cheque_bounce_doc(doc)
		bounce.insert()
		bounce.submit()
		doc.reload()
		self.assertEqual(doc.status, "Bounced")
		self.assertEqual(doc.cheque_bounce, bounce.name)
		self.assertEqual(doc.bounce_reason, "Insufficient Funds")
		self.assertEqual(frappe.db.get_value("Payment Entry", doc.payment_entry, "docstatus"), 2)

	def test_bounce_entry_for_another_cheque_leaves_this_one_alone(self):
		if not frappe.db.exists("DocType", "Cheque Bounce"):
			self.skipTest("field_sales Cheque Bounce not installed")
		mine = self._cheque()
		collect(mine.name, bank_account=self.bank)
		other = self._cheque()
		collect(other.name, bank_account=self.bank)
		bounce = self._cheque_bounce_doc(frappe.get_doc("Post Dated Cheque", other.name))
		bounce.insert()
		bounce.submit()
		mine.reload()
		self.assertEqual(mine.status, "Collected")
		self.assertFalse(mine.cheque_bounce)

	# ---- deposit account from the mode of payment ---------------------

	def _mode_with_account(self):
		mode = frappe.db.get_value("Mode of Payment Account", {"company": COMPANY, "default_account": ["is", "set"]}, "parent")
		if not mode:
			self.skipTest("no mode of payment has an account for this company")
		return mode

	def test_mode_of_payment_account_lookup(self):
		mode = self._mode_with_account()
		account = mode_of_payment_account(mode, COMPANY)
		self.assertEqual(account, frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": COMPANY}, "default_account"))

	def test_collect_uses_the_mode_of_payment_account(self):
		mode = self._mode_with_account()
		account = mode_of_payment_account(mode, COMPANY)
		doc = self._cheque()
		result = collect(doc.name, posting_date=nowdate(), mode_of_payment=mode)
		payment = frappe.get_doc("Payment Entry", result["payment_entry"])
		self.assertEqual(payment.paid_to, account)
		self.assertEqual(payment.mode_of_payment, mode)

	def test_collect_without_an_account_for_the_mode(self):
		mode = frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": f"No Account {frappe.generate_hash(length=4)}", "type": "Bank"}).insert().name
		doc = self._cheque()
		with self.assertRaises(frappe.ValidationError):
			collect(doc.name, mode_of_payment=mode)
		doc.reload()
		self.assertEqual(doc.status, "Pending")

	def test_connections_panel_loads(self):
		from frappe.desk.notifications import get_open_count

		doc = self._cheque()
		collect(doc.name, posting_date=nowdate())
		counts = get_open_count("Post Dated Cheque", doc.name, ["Payment Entry", "Cheque Bounce"])
		found = {row["doctype"]: row for row in counts["count"]["internal_links_found"]}
		self.assertEqual(found["Payment Entry"]["count"], 1)
		self.assertEqual(found["Payment Entry"]["names"], [frappe.db.get_value("Post Dated Cheque", doc.name, "payment_entry")])
		self.assertEqual(found.get("Cheque Bounce", {}).get("count", 0), 0)

		bounce = self._cheque_bounce_doc(frappe.get_doc("Post Dated Cheque", doc.name))
		bounce.insert()
		bounce.submit()
		counts = get_open_count("Post Dated Cheque", doc.name, ["Payment Entry", "Cheque Bounce"])
		found = {row["doctype"]: row for row in counts["count"]["internal_links_found"]}
		self.assertEqual(found["Cheque Bounce"]["names"], [bounce.name])

	# ---- email to whoever entered the cheque --------------------------

	def _reminder_with_mail(self, cheque_date):
		self.bank_account = create_customer_bank_account(self.invoice.customer, "Test Bank", bank_account_no="111000")["name"]
		doc = self._cheque(cheque_date=cheque_date)
		# Administrator is skipped on purpose, so pose as a real user
		owner = frappe.db.get_value("User", {"enabled": 1, "user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]}, "name")
		if not owner:
			self.skipTest("no ordinary user on this site")
		frappe.db.set_value("Post Dated Cheque", doc.name, "owner", owner, update_modified=False)
		doc.owner = owner
		with patch("frappe.sendmail") as mail, patch("chundakadan.utils.push.send_to_users"):
			send_due_reminders()
		return doc, mail

    
	def test_creator_is_emailed_the_day_before_and_on_the_day(self):
		for days in (1, 0):
			frappe.db.rollback()
			ensure_doctypes()
			doc, mail = self._reminder_with_mail(add_days(nowdate(), days))
			sent = [c for c in mail.call_args_list if c.kwargs.get("reference_name") == doc.name]
			self.assertEqual(len(sent), 1, f"{days} days")
			kwargs = sent[0].kwargs
			self.assertEqual(kwargs["recipients"], [frappe.db.get_value("User", doc.owner, "email") or doc.owner])
			self.assertIn(doc.cheque_no, kwargs["subject"])
			self.assertIn("today" if days == 0 else "tomorrow", kwargs["subject"])
			self.assertIn(doc.cheque_no, kwargs["message"])
			self.assertIn(doc.name, kwargs["message"])

	def test_no_email_on_the_other_reminder_days(self):
		for days in (7, 3, 5):
			frappe.db.rollback()
			ensure_doctypes()
			doc, mail = self._reminder_with_mail(add_days(nowdate(), days))
			sent = [c for c in mail.call_args_list if c.kwargs.get("reference_name") == doc.name]
			self.assertEqual(sent, [], f"{days} days")

	# ---- allocating invoices while collecting -------------------------

	def test_outstanding_invoices_lists_open_ones_oldest_first(self):
		rows = outstanding_invoices(self.invoice.customer, COMPANY)
		self.assertTrue(rows)
		self.assertIn(self.invoice.name, [r.sales_invoice for r in rows])
		for row in rows:
			self.assertGreater(flt(row.outstanding_amount), 0)
		dates = [str(r.posting_date) for r in rows]
		self.assertEqual(dates, sorted(dates))

	def test_collect_allocates_what_the_dialog_sends(self):
		outstanding = flt(frappe.db.get_value("Sales Invoice", self.invoice.name, "outstanding_amount"))
		part = round(min(outstanding, 100), 2)
		doc = self._cheque(amount=max(part, 100))
		result = collect(
			doc.name,
			posting_date=nowdate(),
			references=json.dumps([{"sales_invoice": self.invoice.name, "allocated_amount": part}]),
		)
		payment = frappe.get_doc("Payment Entry", result["payment_entry"])
		self.assertEqual([r.reference_name for r in payment.references], [self.invoice.name])
		self.assertAlmostEqual(flt(payment.references[0].allocated_amount), part, places=2)
		after = flt(frappe.db.get_value("Sales Invoice", self.invoice.name, "outstanding_amount"))
		self.assertAlmostEqual(after, outstanding - part, places=2)

	def test_collect_without_allocation_leaves_it_for_reconciliation(self):
		outstanding = flt(frappe.db.get_value("Sales Invoice", self.invoice.name, "outstanding_amount"))
		doc = self._cheque()
		result = collect(doc.name, posting_date=nowdate(), references="[]")
		payment = frappe.get_doc("Payment Entry", result["payment_entry"])
		self.assertEqual(payment.references, [])
		self.assertAlmostEqual(flt(payment.unallocated_amount), flt(doc.amount), places=2)
		self.assertAlmostEqual(
			flt(frappe.db.get_value("Sales Invoice", self.invoice.name, "outstanding_amount")), outstanding, places=2
		)

	def test_allocation_over_the_cheque_amount_is_refused(self):
		doc = self._cheque(amount=100)
		with self.assertRaises(frappe.ValidationError):
			collect(doc.name, references=json.dumps([{"sales_invoice": self.invoice.name, "allocated_amount": 500}]))
		doc.reload()
		self.assertEqual(doc.status, "Pending")

	def test_another_customers_invoice_is_refused(self):
		other = frappe.get_all(
			"Sales Invoice",
			filters={"docstatus": 1, "customer": ["!=", self.invoice.customer], "outstanding_amount": [">", 0]},
			pluck="name",
			limit=1,
		)
		if not other:
			self.skipTest("no other customer's invoice")
		doc = self._cheque()
		with self.assertRaises(frappe.ValidationError):
			collect(doc.name, references=json.dumps([{"sales_invoice": other[0], "allocated_amount": 10}]))
