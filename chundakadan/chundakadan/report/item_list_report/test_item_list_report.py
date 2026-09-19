import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate

from chundakadan.chundakadan.report.item_list_report.item_list_report import execute


class TestItemListReport(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.sample = frappe.db.sql(
			"""select sii.item_code, si.customer, si.company, si.posting_date
			from `tabSales Invoice Item` sii join `tabSales Invoice` si on si.name = sii.parent
			where si.docstatus = 1 and si.is_return = 0 order by si.posting_date desc limit 1""",
			as_dict=True,
		)
		if not self.sample:
			self.skipTest("no submitted Sales Invoice items on this site")
		self.sample = self.sample[0]

	def _run(self, **extra):
		filters = {"company": self.sample.company, "from_date": self.sample.posting_date, "to_date": self.sample.posting_date, **extra}
		return execute(filters)

	def _expected(self, item_code, customer, date):
		return frappe.db.sql(
			"""select sum(sii.stock_qty) qty, count(distinct si.name) n
			from `tabSales Invoice Item` sii join `tabSales Invoice` si on si.name = sii.parent
			where si.docstatus = 1 and si.company = %s and si.posting_date = %s
			and sii.item_code = %s and si.customer = %s""",
			(self.sample.company, date, item_code, customer),
			as_dict=True,
		)[0]

	def test_columns(self):
		columns, _ = self._run()
		names = [c["fieldname"] for c in columns]
		for f in ("item_code", "item_name", "brand", "item_group", "uom", "customer", "customer_name", "qty"):
			self.assertIn(f, names)

	def test_item_filter_lists_customers_with_qty(self):
		_, data = self._run(item_code=self.sample.item_code)
		self.assertTrue(data)
		self.assertTrue(all(r.item_code == self.sample.item_code for r in data))
		row = next(r for r in data if r.customer == self.sample.customer)
		expected = self._expected(self.sample.item_code, self.sample.customer, self.sample.posting_date)
		self.assertAlmostEqual(row.qty, expected.qty)
		self.assertEqual(row.invoices, expected.n)
		item = frappe.db.get_value("Item", self.sample.item_code, ["brand", "item_group", "stock_uom", "item_name"], as_dict=True)
		self.assertEqual((row.brand, row.item_group, row.uom, row.item_name), (item.brand, item.item_group, item.stock_uom, item.item_name))

	def test_one_row_per_item_and_customer(self):
		_, data = self._run()
		keys = [(r.item_code, r.customer) for r in data]
		self.assertEqual(len(keys), len(set(keys)))

	def test_date_range_excludes_other_days(self):
		day_after = add_days(self.sample.posting_date, 1)
		_, data = execute({"company": self.sample.company, "from_date": day_after, "to_date": day_after, "item_code": self.sample.item_code})
		expected = frappe.db.count("Sales Invoice", {"docstatus": 1, "posting_date": day_after, "company": self.sample.company})
		if not expected:
			self.assertEqual(data, [])

	def test_return_reduces_qty(self):
		# a credit note row carries negative stock_qty and must net off
		inv = frappe.get_all("Sales Invoice", {"docstatus": 1, "is_return": 1}, ["name", "company", "posting_date", "customer"], limit=1)
		if not inv:
			self.skipTest("no credit notes on this site")
		inv = inv[0]
		item = frappe.db.get_value("Sales Invoice Item", {"parent": inv.name}, "item_code")
		_, data = execute({"company": inv.company, "from_date": inv.posting_date, "to_date": inv.posting_date, "item_code": item, "customer": inv.customer})
		expected = self._expected(item, inv.customer, inv.posting_date)
		self.assertAlmostEqual(data[0].qty, expected.qty)

	def test_invalid_range(self):
		with self.assertRaises(frappe.ValidationError):
			execute({"company": self.sample.company, "from_date": getdate("2026-09-10"), "to_date": getdate("2026-09-01")})

	def test_roles_can_open_report(self):
		# query_report.get_report_doc needs the report role AND report permission on ref_doctype
		import os
		from frappe.modules.import_file import import_file_by_path

		import_file_by_path(os.path.join(os.path.dirname(__file__), "item_list_report.json"), force=True)
		report = frappe.get_doc("Report", "Item List Report")
		self.assertEqual({r.role for r in report.roles}, {"Accounts User", "Stock User", "Sales User", "System Manager"})
		for role in ("Accounts User", "Stock User", "Sales User"):
			email = f"ilr.{frappe.scrub(role)}@example.com"
			if not frappe.db.exists("User", email):
				frappe.get_doc({"doctype": "User", "email": email, "first_name": role, "send_welcome_email": 0, "user_type": "System User"}).insert()
			user = frappe.get_doc("User", email)
			user.add_roles(role)
			frappe.set_user(email)
			try:
				self.assertTrue(report.is_permitted(), role)
				self.assertTrue(frappe.has_permission(report.ref_doctype, "report"), role)
			finally:
				frappe.set_user("Administrator")
		frappe.db.rollback()

