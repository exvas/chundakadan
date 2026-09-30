import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, today

from chundakadan.chundakadan.report.sales_and_collection_summary.sales_and_collection_summary import (
	GROUPS,
	SALES_ONLY,
	execute,
	get_columns,
)

COMPANY = "Chundakadan Agencies"


class SummaryCase(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.company = frappe.db.get_value("Company", COMPANY, "name") or frappe.db.get_value("Company", {}, "name")
		if not self.company:
			self.skipTest("no company on this site")

	def _run(self, **extra):
		filters = {
			"company": self.company, "from_date": add_days(today(), -365), "to_date": today(),
		}
		filters.update(extra)
		return execute(filters)


class TestColumns(SummaryCase):
	def test_the_first_column_follows_the_grouping(self):
		for group, spec in GROUPS.items():
			columns = get_columns(frappe._dict({"group_by": group}))
			self.assertEqual(columns[0]["fieldname"], "group_value")
			self.assertEqual(columns[0]["fieldtype"], spec["fieldtype"], group)

	def test_sales_columns_are_always_there(self):
		for group in GROUPS:
			names = [c["fieldname"] for c in get_columns(frappe._dict({"group_by": group}))]
			for field in ("sales", "invoices", "qty"):
				self.assertIn(field, names, group)

	def test_brand_hides_the_collection_columns(self):
		"""A payment is not made against an invoice line, so it cannot be
		attributed to a brand -- better to omit the column than to show a
		zero that looks like nothing was collected."""
		for group in SALES_ONLY:
			names = [c["fieldname"] for c in get_columns(frappe._dict({"group_by": group}))]
			self.assertNotIn("collection", names, group)
			self.assertNotIn("balance", names, group)

	def test_every_other_grouping_shows_collection(self):
		for group in GROUPS:
			if group in SALES_ONLY:
				continue
			names = [c["fieldname"] for c in get_columns(frappe._dict({"group_by": group}))]
			for field in ("collection", "receipts", "balance"):
				self.assertIn(field, names, group)


class TestFilterValidation(SummaryCase):
	def test_the_dates_are_required(self):
		with self.assertRaises(frappe.ValidationError):
			execute({"company": self.company, "from_date": today()})
		with self.assertRaises(frappe.ValidationError):
			execute({"company": self.company, "to_date": today()})

	def test_a_reversed_range_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self._run(from_date=today(), to_date=add_days(today(), -1))

	def test_an_unknown_grouping_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self._run(group_by="Phase of the Moon")

	def test_sales_person_is_the_default_grouping(self):
		columns, _data = self._run()
		self.assertEqual(columns[0]["options"], "Sales Person")


class TestTheNumbers(SummaryCase):
	def setUp(self):
		super().setUp()
		if not frappe.db.exists("Sales Invoice", {"docstatus": 1, "company": self.company}):
			self.skipTest("no submitted invoices on this site")

	def test_the_sales_total_matches_the_invoices(self):
		_columns, data = self._run()
		expected = frappe.db.sql(
			"""select sum(sii.base_net_amount) from `tabSales Invoice Item` sii
			join `tabSales Invoice` si on si.name = sii.parent
			where si.docstatus = 1 and si.company = %s and si.posting_date between %s and %s""",
			(self.company, add_days(today(), -365), today()),
		)[0][0]
		self.assertAlmostEqual(sum(flt(r["sales"]) for r in data), flt(expected), places=2)

	def test_the_collection_total_matches_the_receipts(self):
		_columns, data = self._run()
		expected = frappe.db.sql(
			"""select sum(base_paid_amount) from `tabPayment Entry`
			where docstatus = 1 and company = %s and payment_type = 'Receive'
			  and party_type = 'Customer' and posting_date between %s and %s""",
			(self.company, add_days(today(), -365), today()),
		)[0][0]
		self.assertAlmostEqual(
			sum(flt(r["collection"]) for r in data), flt(expected or 0), places=2
		)

	def test_balance_is_sales_less_collection_on_every_row(self):
		_columns, data = self._run()
		for row in data:
			self.assertAlmostEqual(
				flt(row["balance"]), flt(row["sales"]) - flt(row["collection"]), places=2
			)

	def test_grouping_by_brand_totals_the_same_sales(self):
		_columns, by_person = self._run()
		_columns, by_brand = self._run(group_by="Brand")
		self.assertAlmostEqual(
			sum(flt(r["sales"]) for r in by_brand),
			sum(flt(r["sales"]) for r in by_person),
			places=2,
			msg="the same sales, cut a different way",
		)

	def test_months_come_back_in_order(self):
		_columns, data = self._run(group_by="Month")
		if len(data) < 2:
			self.skipTest("needs more than one month of data")
		labels = [r["group_value"] for r in data]
		months = [frappe.utils.getdate("01 " + label) for label in labels]
		self.assertEqual(months, sorted(months), f"months out of order: {labels}")

	def test_days_come_back_in_order(self):
		_columns, data = self._run(group_by="Day")
		values = [str(r["group_value"]) for r in data]
		self.assertEqual(values, sorted(values))

	def test_a_rows_with_no_sales_person_is_labelled_not_set(self):
		_columns, data = self._run()
		blank = [r for r in data if r["group_value"] == "(not set)"]
		unassigned = frappe.db.count(
			"Sales Invoice",
			{"docstatus": 1, "company": self.company, "custom_sales_person": ["in", ["", None]]},
		)
		if unassigned:
			self.assertTrue(blank, "unassigned invoices must still be shown")

	def test_filtering_by_sales_person_narrows_it(self):
		person = frappe.db.get_value(
			"Sales Invoice", {"docstatus": 1, "company": self.company,
			                  "custom_sales_person": ["not in", ["", None]]}, "custom_sales_person"
		)
		if not person:
			self.skipTest("no invoice carries a sales person")
		_columns, data = self._run(sales_person=person)
		self.assertTrue(all(r["group_value"] == person for r in data))
