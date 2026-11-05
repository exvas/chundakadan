"""What a customer owes, and whose job it is to collect it."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate, today

from chundakadan.chundakadan.report.customer_dues.customer_dues import execute
from chundakadan.testing import a_company, a_customer, a_stock_item, a_warehouse


class DuesCase(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.company = a_company()
		self.customer = a_customer(self.company) if self.company else None
		self.item = a_stock_item()
		self.warehouse = a_warehouse(self.company) if self.company else None
		if not (self.company and self.customer and self.item):
			self.skipTest("this bench cannot build a Sales Invoice")
		self._clear_previous()
		self.person = self._a_sales_person()

	def _clear_previous(self):
		"""A submitted invoice outlives the per-test rollback, so each test
		starts with only the ones it raised itself."""
		names = frappe.get_all("Sales Invoice", filters={"customer": self.customer}, pluck="name")
		if not names:
			return
		frappe.db.delete("GL Entry", {"voucher_type": "Sales Invoice", "voucher_no": ["in", names]})
		frappe.db.delete("Sales Invoice Item", {"parent": ["in", names]})
		frappe.db.delete("Sales Invoice", {"name": ["in", names]})

	def _a_sales_person(self):
		name = frappe.db.get_value("Sales Person", {"enabled": 1}, "name", order_by="name asc")
		if name:
			return name
		doc = frappe.get_doc(
			{"doctype": "Sales Person", "sales_person_name": "_Test Dues Person", "is_group": 0}
		)
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		return doc.name

	def _invoice(self, amount, sales_person=None, posting_date=None, due_date=None, paid=0):
		# ERPNext refuses a due date before the posting date, so an invoice
		# that is already overdue has to have been raised earlier too
		posting_date = posting_date or (
			due_date if due_date and getdate(due_date) < getdate(today()) else today()
		)
		doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": self.customer,
				"company": self.company,
				"currency": frappe.get_cached_value("Company", self.company, "default_currency"),
				"conversion_rate": 1,
				"posting_date": posting_date,
				"set_posting_time": 1,
				"due_date": due_date or today(),
				"custom_sales_person": sales_person,
				# the credit restriction refuses a new invoice for a customer
				# who is already overdue, which is exactly the customer these
				# tests need; this is the app's own way past it
				"custom_ignore_overdue_restriction": 1,
				"items": [
					{
						"item_code": self.item,
						"qty": 1,
						"rate": amount,
						"warehouse": self.warehouse,
					}
				],
			}
		)
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		doc.submit()
		if paid:
			frappe.db.set_value(
				"Sales Invoice", doc.name, "outstanding_amount", doc.outstanding_amount - paid
			)
		return doc

	def _run(self, **extra):
		filters = {"company": self.company}
		filters.update(extra)
		return execute(filters)


class TestWhatIsOwed(DuesCase):
	def test_an_unpaid_invoice_is_a_due(self):
		self._invoice(1000, sales_person=self.person)
		_columns, rows = self._run(customer=self.customer)
		self.assertEqual(len(rows), 1)
		self.assertEqual(flt(rows[0]["outstanding"], 2), 1000)
		self.assertEqual(rows[0]["invoices"], 1)

	def test_a_settled_invoice_is_not(self):
		self._invoice(1000, sales_person=self.person, paid=1000)
		_columns, rows = self._run(customer=self.customer)
		self.assertEqual(rows, [])

	def test_a_part_payment_leaves_the_rest(self):
		self._invoice(1000, sales_person=self.person, paid=400)
		_columns, rows = self._run(customer=self.customer)
		self.assertEqual(flt(rows[0]["outstanding"], 2), 600)

	def test_there_is_no_date_range(self):
		"""A due is a due whenever it was billed -- this is the thing the
		Sales and Collection Summary's Balance is not."""
		self._invoice(5000, sales_person=self.person, posting_date=add_days(today(), -300))
		_columns, rows = self._run(customer=self.customer)
		self.assertEqual(flt(rows[0]["outstanding"], 2), 5000)

	def test_several_invoices_add_up_under_one_customer(self):
		self._invoice(1000, sales_person=self.person)
		self._invoice(2500, sales_person=self.person)
		_columns, rows = self._run(customer=self.customer, sales_person=self.person)
		self.assertEqual(len(rows), 1)
		self.assertEqual(flt(rows[0]["outstanding"], 2), 3500)
		self.assertEqual(rows[0]["invoices"], 2)


class TestWhoCollectsIt(DuesCase):
	def test_the_invoice_s_own_sales_person_owns_it(self):
		self._invoice(1000, sales_person=self.person)
		_columns, rows = self._run(customer=self.customer, sales_person=self.person)
		self.assertEqual(rows[0]["sales_person"], self.person)

	def test_an_invoice_with_nobody_falls_to_the_customer_s_sales_person(self):
		"""Every opening invoice carries no sales person. Selling is
		history; collecting is somebody's job today, so the debt follows
		whoever has the customer now."""
		customer = frappe.get_doc("Customer", self.customer)
		customer.set("sales_team", [])
		customer.append("sales_team", {"sales_person": self.person, "allocated_percentage": 100})
		customer.flags.ignore_mandatory = True
		customer.save(ignore_permissions=True)

		self._invoice(1200, sales_person=None)
		_columns, rows = self._run(customer=self.customer, sales_person=self.person)
		self.assertEqual(len(rows), 1, "the customer's own sales person should have picked it up")
		self.assertEqual(flt(rows[0]["outstanding"], 2), 1200)

	def test_the_sales_person_filter_leaves_somebody_else_s_out(self):
		other = frappe.db.get_value(
			"Sales Person", {"enabled": 1, "name": ["!=", self.person]}, "name", order_by="name asc"
		)
		if not other:
			self.skipTest("this bench has only one sales person")
		self._invoice(1000, sales_person=self.person)
		self._invoice(7000, sales_person=other)
		_columns, rows = self._run(customer=self.customer, sales_person=self.person)
		self.assertEqual(flt(sum(r["outstanding"] for r in rows), 2), 1000)


class TestAging(DuesCase):
	def test_an_invoice_past_its_due_date_is_overdue(self):
		self._invoice(1000, sales_person=self.person, due_date=add_days(today(), -10))
		_columns, rows = self._run(customer=self.customer)
		self.assertEqual(rows[0]["days_overdue"], 10)

	def test_one_not_yet_due_is_not(self):
		self._invoice(1000, sales_person=self.person, due_date=add_days(today(), 10))
		_columns, rows = self._run(customer=self.customer)
		self.assertEqual(rows[0]["days_overdue"], 0)

	def test_the_customer_row_ages_from_its_oldest_bill(self):
		self._invoice(1000, sales_person=self.person, due_date=add_days(today(), -40))
		self._invoice(1000, sales_person=self.person, due_date=add_days(today(), -5))
		_columns, rows = self._run(customer=self.customer, sales_person=self.person)
		self.assertEqual(rows[0]["days_overdue"], 40)


class TestInvoiceDetail(DuesCase):
	def test_the_detail_lists_each_open_invoice(self):
		self._invoice(1000, sales_person=self.person)
		self._invoice(2500, sales_person=self.person)
		self._invoice(400, sales_person=self.person, paid=400)
		_columns, rows = self._run(customer=self.customer, detail=1)
		self.assertEqual(len(rows), 2)

	def test_the_rows_add_up_to_the_customer_figure(self):
		self._invoice(1000, sales_person=self.person)
		self._invoice(2500, sales_person=self.person)
		summary = self._run(customer=self.customer, sales_person=self.person)[1]
		detail = self._run(customer=self.customer, sales_person=self.person, detail=1)[1]
		self.assertEqual(
			flt(sum(r["outstanding"] for r in detail), 2),
			flt(sum(r["outstanding"] for r in summary), 2),
		)

	def test_the_oldest_comes_first(self):
		self._invoice(1000, sales_person=self.person, due_date=add_days(today(), -5))
		self._invoice(2500, sales_person=self.person, due_date=add_days(today(), -40))
		detail = self._run(customer=self.customer, detail=1)[1]
		self.assertEqual(getdate(detail[0]["due_date"]), getdate(add_days(today(), -40)))

	def test_it_carries_what_somebody_chasing_needs(self):
		self._invoice(1000, sales_person=self.person)
		row = self._run(customer=self.customer, detail=1)[1][0]
		for field in ("invoice", "posting_date", "due_date", "customer", "outstanding", "grand_total"):
			self.assertIsNotNone(row.get(field), field)

	def test_the_columns_change_with_the_tick(self):
		summary_columns = [c["fieldname"] for c in self._run(customer=self.customer)[0]]
		detail_columns = [c["fieldname"] for c in self._run(customer=self.customer, detail=1)[0]]
		self.assertIn("invoices", summary_columns)
		self.assertNotIn("invoice", summary_columns)
		self.assertIn("invoice", detail_columns)


class TestFilters(DuesCase):
	def test_the_company_is_required(self):
		with self.assertRaises(frappe.ValidationError):
			execute({})

	def test_another_company_s_invoice_is_not_counted(self):
		other = frappe.db.get_value("Company", {"name": ["!=", self.company]}, "name", order_by="name asc")
		if not other:
			self.skipTest("this bench has only one company")
		self._invoice(1000, sales_person=self.person)
		_columns, rows = self._run(company=other, customer=self.customer)
		self.assertEqual(rows, [])

	def test_the_territory_filter_narrows_it(self):
		self._invoice(1000, sales_person=self.person)
		territory = frappe.db.get_value("Customer", self.customer, "territory")
		if not territory:
			self.skipTest("the test customer has no territory")
		_columns, rows = self._run(customer=self.customer, territory=territory)
		self.assertTrue(rows)
		self.assertEqual({r["territory"] for r in rows}, {territory})
