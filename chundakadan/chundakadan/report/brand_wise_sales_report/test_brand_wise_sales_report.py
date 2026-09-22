import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate

from chundakadan.chundakadan.report.brand_wise_sales_report.brand_wise_sales_report import execute

COMPANY = "Chundakadan Agencies"


class TestBrandWiseSalesReport(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		row = frappe.db.sql(
			"""select si.posting_date, si.custom_sales_person, si.name
			from `tabSales Invoice` si join `tabSales Invoice Item` sii on sii.parent = si.name
			where si.docstatus = 1 and si.company = %s order by si.posting_date desc limit 1""",
			COMPANY, as_dict=True,
		)
		if not row:
			self.skipTest("no submitted invoices")
		self.sample = row[0]

	def _run(self, **extra):
		return execute({"company": COMPANY, "from_date": self.sample.posting_date, "to_date": self.sample.posting_date, **extra})

	def test_columns(self):
		columns, _data = self._run()
		self.assertEqual([c["fieldname"] for c in columns], ["brand", "amount", "qty", "invoices", "customers"])

	def test_totals_match_the_invoice_lines(self):
		_columns, data = self._run()
		expected = frappe.db.sql(
			"""select sum(sii.base_net_amount) as amount
			from `tabSales Invoice Item` sii join `tabSales Invoice` si on si.name = sii.parent
			where si.docstatus = 1 and si.company = %s and si.posting_date = %s""",
			(COMPANY, self.sample.posting_date), as_dict=True,
		)[0]
		self.assertAlmostEqual(sum(flt(r.amount) for r in data), flt(expected.amount), places=2)

	def test_one_row_per_brand(self):
		_columns, data = self._run()
		brands = [r.brand for r in data]
		self.assertEqual(len(brands), len(set(brands)))
		for row in data:
			self.assertTrue(row.brand)

	def test_brand_matches_the_item_master(self):
		_columns, data = self._run()
		if not data:
			self.skipTest("no sales that day")
		brand = data[0].brand
		if brand == "Without Brand":
			self.skipTest("top row is unbranded")
		expected = frappe.db.sql(
			"""select sum(sii.base_net_amount) as amount
			from `tabSales Invoice Item` sii
			join `tabSales Invoice` si on si.name = sii.parent
			join `tabItem` item on item.name = sii.item_code
			where si.docstatus = 1 and si.company = %s and si.posting_date = %s and item.brand = %s""",
			(COMPANY, self.sample.posting_date, brand), as_dict=True,
		)[0]
		self.assertAlmostEqual(flt(data[0].amount), flt(expected.amount), places=2)

	def test_sales_person_filter(self):
		if not self.sample.custom_sales_person:
			self.skipTest("invoice has no sales person")
		_columns, data = self._run(sales_person=self.sample.custom_sales_person)
		expected = frappe.db.sql(
			"""select sum(sii.base_net_amount) as amount
			from `tabSales Invoice Item` sii join `tabSales Invoice` si on si.name = sii.parent
			where si.docstatus = 1 and si.company = %s and si.posting_date = %s and si.custom_sales_person = %s""",
			(COMPANY, self.sample.posting_date, self.sample.custom_sales_person), as_dict=True,
		)[0]
		self.assertAlmostEqual(sum(flt(r.amount) for r in data), flt(expected.amount), places=2)

	def test_date_range_is_respected(self):
		day_before = add_days(self.sample.posting_date, -1)
		_columns, data = execute({"company": COMPANY, "from_date": day_before, "to_date": day_before})
		expected = frappe.db.sql(
			"""select count(*) as n from `tabSales Invoice` where docstatus = 1 and company = %s and posting_date = %s""",
			(COMPANY, day_before), as_dict=True,
		)[0]
		if not expected.n:
			self.assertEqual(data, [])

	def test_invalid_range_and_missing_dates(self):
		with self.assertRaises(frappe.ValidationError):
			execute({"company": COMPANY, "from_date": getdate("2026-09-10"), "to_date": getdate("2026-09-01")})
		with self.assertRaises(frappe.ValidationError):
			execute({"company": COMPANY})

	def test_accounts_user_and_sales_user_can_open_it(self):
		import os

		from frappe.modules.import_file import import_file_by_path

		import_file_by_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "brand_wise_sales_report.json"), force=True)
		report = frappe.get_doc("Report", "Brand Wise Sales Report")
		self.assertTrue({"Accounts User", "Sales User"}.issubset({r.role for r in report.roles}))

		for role in ("Accounts User", "Sales User"):
			email = f"bwsr.{frappe.scrub(role)}@example.com"
			if not frappe.db.exists("User", email):
				frappe.get_doc({"doctype": "User", "email": email, "first_name": role, "send_welcome_email": 0, "user_type": "System User"}).insert()
			frappe.get_doc("User", email).add_roles(role)
			frappe.set_user(email)
			try:
				# query_report needs the report role AND report permission on ref_doctype
				self.assertTrue(report.is_permitted(), role)
				self.assertTrue(frappe.has_permission(report.ref_doctype, "report"), role)
			finally:
				frappe.set_user("Administrator")
		frappe.db.rollback()
