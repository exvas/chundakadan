import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, today

from chundakadan.chundakadan.report.gst_sales_register_report.gst_sales_register_report import (
	_rate,
	_state_code,
	execute,
)

COMPANY = "Chundakadan Agencies"

#: the sheet the old software produced, column for column
SHEET_COLUMNS = [
	"SlNo", "Date", "Voucher No", "Party Name", "City", "State", "State Code",
	"GST No", "HSN", "Item group", "Amount", "SGST%", "CGST%", "IGST%",
	"CGST", "SGST", "IGSTA", "CESS", "Total", "Qty", "Unit", "Discount",
]


class RegisterCase(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.company = COMPANY
		if not frappe.db.exists("Company", self.company):
			self.skipTest("company not on this site")

	def _run(self, **overrides):
		filters = {
			"company": self.company,
			"from_date": add_days(today(), -365),
			"to_date": today(),
		}
		filters.update(overrides)
		return execute(filters)


class TestTheLayout(RegisterCase):
	def test_the_columns_match_the_sheet(self):
		columns, _data = self._run()
		self.assertEqual([c["label"] for c in columns], SHEET_COLUMNS)

	def test_the_dates_are_required(self):
		with self.assertRaises(frappe.ValidationError):
			execute({"company": self.company, "from_date": today()})

	def test_a_reversed_range_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self._run(from_date=today(), to_date=add_days(today(), -5))

	def test_the_rates_are_not_summed_in_the_total_row(self):
		"""They are labels, not money — Data keeps them out of the total."""
		columns, _data = self._run()
		by_name = {c["fieldname"]: c for c in columns}
		for field in ("sgst_rate", "cgst_rate", "igst_rate"):
			self.assertEqual(by_name[field]["fieldtype"], "Data")


class TestTheNumbers(RegisterCase):
	def setUp(self):
		super().setUp()
		_columns, self.data = self._run()
		if not self.data:
			self.skipTest("no invoices on this site")

	def test_total_is_the_taxable_value_plus_the_tax(self):
		for row in self.data:
			self.assertAlmostEqual(
				flt(row["total"]),
				flt(row["amount"]) + flt(row["cgst"]) + flt(row["sgst"])
				+ flt(row["igst"]) + flt(row["cess"]),
				places=2,
				msg=row["voucher_no"],
			)

	def test_the_taxable_total_matches_the_invoices(self):
		expected = frappe.db.sql(
			"""select sum(base_net_total) from `tabSales Invoice`
			where docstatus = 1 and company = %s and posting_date between %s and %s""",
			(self.company, add_days(today(), -365), today()),
		)[0][0]
		self.assertAlmostEqual(
			sum(flt(r["amount"]) for r in self.data), flt(expected), places=2
		)

	def test_the_tax_total_matches_the_invoices(self):
		expected = frappe.db.sql(
			"""select sum(ifnull(sii.cgst_amount, 0) + ifnull(sii.sgst_amount, 0)
			          + ifnull(sii.igst_amount, 0))
			from `tabSales Invoice Item` sii join `tabSales Invoice` si on si.name = sii.parent
			where si.docstatus = 1 and si.company = %s and si.posting_date between %s and %s""",
			(self.company, add_days(today(), -365), today()),
		)[0][0]
		got = sum(flt(r["cgst"]) + flt(r["sgst"]) + flt(r["igst"]) for r in self.data)
		self.assertAlmostEqual(got, flt(expected or 0), places=2)

	def test_the_serial_numbers_run_from_one(self):
		self.assertEqual([r["sl_no"] for r in self.data][:3], ["1", "2", "3"][: len(self.data)])

	def test_a_row_is_one_invoice_one_hsn_one_brand(self):
		keys = [(r["voucher_no"], r["hsn"], r["item_group"]) for r in self.data]
		self.assertEqual(len(keys), len(set(keys)))

	def test_filtering_by_customer_narrows_it(self):
		customer = self.data[0]["voucher_no"]
		customer = frappe.db.get_value("Sales Invoice", customer, "customer")
		_columns, narrowed = self._run(customer=customer)
		self.assertTrue(narrowed)
		for row in narrowed:
			self.assertEqual(
				frappe.db.get_value("Sales Invoice", row["voucher_no"], "customer"), customer
			)


class TestTheHelpers(RegisterCase):
	def test_a_whole_rate_loses_its_decimal(self):
		self.assertEqual(_rate(9.0), "9")
		self.assertEqual(_rate(2.5), "2.5")

	def test_a_rate_that_is_not_charged_is_blank(self):
		self.assertIsNone(_rate(0))
		self.assertIsNone(_rate(None))

	def test_the_state_code_comes_off_the_place_of_supply(self):
		self.assertEqual(_state_code({"place_of_supply": "32-Kerala"}), "32")

	def test_it_falls_back_to_the_gstin(self):
		self.assertEqual(_state_code({"place_of_supply": "", "gst_no": "29AAAAA0000A1Z5"}), "29")

	def test_with_neither_it_is_blank(self):
		self.assertIsNone(_state_code({"place_of_supply": None, "gst_no": None}))
