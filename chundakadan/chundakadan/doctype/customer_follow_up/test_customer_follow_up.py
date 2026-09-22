import os

import frappe
from frappe.modules.import_file import import_file_by_path
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate

from chundakadan.chundakadan.doctype.customer_follow_up.customer_follow_up import (
	chase_history,
	customer_outstanding,
)

COMPANY = "Chundakadan Agencies"


def ensure_doctype():
	import_file_by_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "customer_follow_up.json"), force=True)


class TestCustomerFollowUp(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		ensure_doctype()
		invoice = frappe.get_all(
			"Sales Invoice",
			filters={"docstatus": 1, "company": COMPANY, "outstanding_amount": [">", 0]},
			fields=["customer"],
			limit=1,
		)
		if not invoice:
			self.skipTest("no customer with outstanding")
		self.customer = invoice[0].customer

	def tearDown(self):
		frappe.db.rollback()

	def _follow_up(self, **values):
		doc = frappe.get_doc({
			"doctype": "Customer Follow Up",
			"customer": self.customer,
			"company": COMPANY,
			"follow_up_date": nowdate(),
			"outcome": "Called",
			"next_follow_up_date": add_days(nowdate(), 3),
			"remarks": "spoke to the accountant",
			**values,
		})
		doc.insert()
		doc.reload()
		return doc

	def test_outstanding_is_stamped_from_the_invoices(self):
		doc = self._follow_up()
		self.assertAlmostEqual(flt(doc.outstanding_amount), flt(customer_outstanding(self.customer, COMPANY)), places=2)
		self.assertGreater(flt(doc.outstanding_amount), 0)

	def test_a_task_is_created_for_the_next_date(self):
		doc = self._follow_up()
		self.assertTrue(doc.todo)
		todo = frappe.get_doc("ToDo", doc.todo)
		self.assertEqual(str(todo.date), str(add_days(nowdate(), 3)))
		self.assertEqual(todo.status, "Open")
		self.assertEqual((todo.reference_type, todo.reference_name), ("Customer Follow Up", doc.name))
		self.assertIn(doc.customer_name or doc.customer, todo.description)

	def test_logging_the_next_one_closes_the_previous(self):
		first = self._follow_up()
		second = self._follow_up(outcome="Promised to Pay", promised_amount=5000)
		first.reload()
		self.assertEqual(first.status, "Closed")
		self.assertEqual(frappe.db.get_value("ToDo", first.todo, "status"), "Closed")
		self.assertEqual(second.status, "Open")
		self.assertEqual(frappe.db.get_value("ToDo", second.todo, "status"), "Open")

	def test_paid_closes_the_chase_without_a_next_date(self):
		doc = self._follow_up(outcome="Paid", next_follow_up_date=None)
		self.assertEqual(doc.status, "Closed")
		self.assertFalse(doc.next_follow_up_date)
		self.assertFalse(doc.todo)

	def test_next_date_is_required_unless_paid(self):
		with self.assertRaises(frappe.ValidationError):
			self._follow_up(next_follow_up_date=None)

	def test_next_date_cannot_be_before_the_follow_up(self):
		with self.assertRaises(frappe.ValidationError):
			self._follow_up(next_follow_up_date=add_days(nowdate(), -1))

	def test_promised_amount_only_for_a_promise(self):
		doc = self._follow_up(outcome="Called", promised_amount=1000)
		self.assertEqual(flt(doc.promised_amount), 0)
		promised = self._follow_up(outcome="Promised to Pay", promised_amount=1000)
		self.assertEqual(flt(promised.promised_amount), 1000)

	def test_chase_history_lists_newest_first(self):
		first = self._follow_up(follow_up_date=add_days(nowdate(), -5), next_follow_up_date=add_days(nowdate(), -1))
		second = self._follow_up()
		history = chase_history(self.customer, COMPANY)
		self.assertEqual([row["name"] for row in history][:2], [second.name, first.name])

	def test_accounts_user_can_log_one(self):
		meta_roles = {p.role: p for p in frappe.get_meta("Customer Follow Up").permissions}
		self.assertIn("Accounts User", meta_roles)
		self.assertEqual((meta_roles["Accounts User"].read, meta_roles["Accounts User"].write, meta_roles["Accounts User"].create), (1, 1, 1))
		self.assertEqual(meta_roles["Accounts User"].delete, 0)

	def test_deleting_removes_its_task(self):
		doc = self._follow_up()
		todo = doc.todo
		doc.delete()
		self.assertFalse(frappe.db.exists("ToDo", todo))
