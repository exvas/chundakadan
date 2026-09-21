import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate

from unittest.mock import patch

from chundakadan.chundakadan.doctype.post_dated_cheque.post_dated_cheque import collect, mark_bounced, reminder_recipients, send_due_reminders
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
			"bank_name": "SBI",
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

	def test_sales_person_falls_back_to_the_customer_team(self):
		person = frappe.db.get_value("Sales Team", {"parent": self.invoice.customer, "parenttype": "Customer"}, "sales_person")
		doc = self._cheque()
		self.assertEqual(doc.sales_person, person)

	def test_sales_person_kept_when_set(self):
		person = frappe.db.get_value("Sales Person", {"enabled": 1}, "name")
		doc = self._cheque(sales_person=person, references=[{"sales_invoice": self.invoice.name}])
		self.assertEqual(doc.sales_person, person)

	def _reminder_run(self, cheque_date):
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
