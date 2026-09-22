import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate

from chundakadan.chundakadan.report.stock_out_by_customer.stock_out_by_customer import execute

COMPANY = "Chundakadan Agencies"


class TestStockOutByCustomer(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		row = frappe.db.sql(
			"""select sle.posting_date, sle.item_code, sle.warehouse, sle.voucher_type, sle.voucher_no
			from `tabStock Ledger Entry` sle
			where sle.is_cancelled = 0 and sle.company = %s and sle.actual_qty < 0
			  and sle.voucher_type in ('Delivery Note', 'Sales Invoice')
			order by sle.posting_date desc limit 1""",
			COMPANY, as_dict=True,
		)
		if not row:
			self.skipTest("no stock going out on this site")
		self.sample = row[0]
		self.customer = frappe.db.get_value(self.sample.voucher_type, self.sample.voucher_no, "customer")

	def _run(self, **extra):
		return execute({"company": COMPANY, "from_date": self.sample.posting_date, "to_date": self.sample.posting_date, **extra})

	def test_columns(self):
		columns, _data = self._run()
		names = [c["fieldname"] for c in columns]
		for field in ("item_code", "item_name", "customer", "customer_name", "qty", "uom", "value"):
			self.assertIn(field, names)

	def test_quantities_are_positive_and_match_the_ledger(self):
		_columns, data = self._run()
		self.assertTrue(data)
		for row in data:
			self.assertGreater(flt(row.qty), 0, row.item_code)
			self.assertTrue(row.customer)
		expected = frappe.db.sql(
			"""select -sum(actual_qty) as qty from `tabStock Ledger Entry`
			where is_cancelled = 0 and company = %s and posting_date = %s
			  and voucher_type in ('Delivery Note', 'Sales Invoice')""",
			(COMPANY, self.sample.posting_date), as_dict=True,
		)[0]
		self.assertAlmostEqual(sum(flt(r.qty) for r in data), flt(expected.qty), places=3)

	def test_the_sample_item_shows_its_customer(self):
		_columns, data = self._run(item_code=self.sample.item_code)
		self.assertTrue(data)
		self.assertIn(self.customer, [r.customer for r in data])
		for row in data:
			self.assertEqual(row.item_code, self.sample.item_code)

	def test_customer_filter(self):
		_columns, data = self._run(customer=self.customer)
		self.assertTrue(all(r.customer == self.customer for r in data))

	def test_item_details_come_from_the_item_master(self):
		_columns, data = self._run(item_code=self.sample.item_code)
		item = frappe.db.get_value("Item", self.sample.item_code, ["item_name", "brand", "stock_uom"], as_dict=True)
		self.assertEqual((data[0].item_name, data[0].brand, data[0].uom), (item.item_name, item.brand, item.stock_uom))

	def test_a_quiet_day_is_empty(self):
		day = add_days(self.sample.posting_date, -1)
		moved = frappe.db.count("Stock Ledger Entry", {"company": COMPANY, "posting_date": day, "is_cancelled": 0, "voucher_type": ["in", ["Delivery Note", "Sales Invoice"]]})
		_columns, data = execute({"company": COMPANY, "from_date": day, "to_date": day})
		if not moved:
			self.assertEqual(data, [])

	def test_invalid_range_and_missing_dates(self):
		with self.assertRaises(frappe.ValidationError):
			execute({"company": COMPANY, "from_date": getdate("2026-09-10"), "to_date": getdate("2026-09-01")})
		with self.assertRaises(frappe.ValidationError):
			execute({"company": COMPANY})

	def test_roles_can_open_it(self):
		import os

		from frappe.modules.import_file import import_file_by_path

		import_file_by_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_out_by_customer.json"), force=True)
		report = frappe.get_doc("Report", "Stock Out by Customer")
		self.assertTrue({"Accounts User", "Sales User", "Stock User"}.issubset({r.role for r in report.roles}))
		for role in ("Accounts User", "Sales User", "Stock User"):
			email = f"sobc.{frappe.scrub(role)}@example.com"
			if not frappe.db.exists("User", email):
				frappe.get_doc({"doctype": "User", "email": email, "first_name": role, "send_welcome_email": 0, "user_type": "System User"}).insert()
			frappe.get_doc("User", email).add_roles(role)
			frappe.set_user(email)
			try:
				self.assertTrue(report.is_permitted(), role)
				self.assertTrue(frappe.has_permission(report.ref_doctype, "report"), role)
			finally:
				frappe.set_user("Administrator")
		frappe.db.rollback()
