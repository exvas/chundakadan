from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, today

from chundakadan.chundakadan.report.sales_and_collection_summary import sales_and_collection_summary as report
from chundakadan.chundakadan.report.sales_and_collection_summary.sales_and_collection_summary import (
	GROUPS,
	NOT_AN_OPENING,
	SALES_ONLY,
	execute,
	get_columns,
)

COMPANY = "Chundakadan Agencies"


class SummaryCase(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.company = frappe.db.get_value("Company", COMPANY, "name") or frappe.db.get_value(
			"Company", {}, "name"
		)
		if not self.company:
			self.skipTest("no company on this site")

	def _run(self, **extra):
		filters = {
			"company": self.company,
			"from_date": add_days(today(), -365),
			"to_date": today(),
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

	def test_the_sales_total_matches_the_sales_register(self):
		"""The register shows the grand total, and so must this."""
		_columns, data = self._run()
		expected = frappe.db.sql(
			"""select sum(base_grand_total) from `tabSales Invoice`
			where docstatus = 1 and company = %s and posting_date between %s and %s
			  and ifnull(is_opening, '') <> 'Yes'""",
			(self.company, add_days(today(), -365), today()),
		)[0][0]
		self.assertAlmostEqual(sum(flt(r["sales"]) for r in data), flt(expected), places=2)

	def test_an_opening_balance_is_not_somebody_sales(self):
		"""The invoices raised to carry the old software's balances over are
		dated the day the books were opened. Counted as sales they would hand
		each salesman his whole inherited ledger as one month's selling."""
		opening = frappe.db.sql(
			"""select sum(base_grand_total) from `tabSales Invoice`
			where docstatus = 1 and company = %s and posting_date between %s and %s
			  and is_opening = 'Yes'""",
			(self.company, add_days(today(), -365), today()),
		)[0][0]
		if not opening:
			self.skipTest("no opening invoices in the window on this site")

		_columns, data = self._run()
		everything = frappe.db.sql(
			"""select sum(base_grand_total) from `tabSales Invoice`
			where docstatus = 1 and company = %s and posting_date between %s and %s""",
			(self.company, add_days(today(), -365), today()),
		)[0][0]
		reported = sum(flt(r["sales"]) for r in data)
		self.assertAlmostEqual(reported, flt(everything) - flt(opening), places=2)
		self.assertLess(reported, flt(everything), "the opening is still being counted as sales")

	def test_the_opening_is_left_out_whichever_way_it_is_grouped(self):
		"""Sales Person reads the invoice total, Brand sums the lines — two
		different queries, and the opening has to be absent from both."""
		totals = {}
		for group in ("Sales Person", "Customer", "Month"):
			_columns, data = self._run(group_by=group)
			totals[group] = round(sum(flt(r["sales"]) for r in data), 2)
		self.assertEqual(len(set(totals.values())), 1, f"groupings disagree: {totals}")

	def test_the_label_says_the_tax_is_in_it(self):
		"""The Brand Wise Sales Report shows a brand WITHOUT the tax; if the
		labels do not say which is which, the two look like a discrepancy."""
		columns, _data = self._run()
		sales = next(c for c in columns if c["fieldname"] == "sales")
		self.assertIn("incl. GST", sales["label"])

	def test_the_sales_figure_includes_the_tax(self):
		"""Summing base_net_amount stripped the GST out and put the report
		below the register -- the bug this guards."""
		_columns, data = self._run()
		net, tax = frappe.db.sql(
			"""select sum(base_net_total), sum(base_total_taxes_and_charges)
			from `tabSales Invoice`
			where docstatus = 1 and company = %s and posting_date between %s and %s""",
			(self.company, add_days(today(), -365), today()),
		)[0]
		if not flt(tax):
			self.skipTest("no taxed invoices on this site")
		total = sum(flt(r["sales"]) for r in data)
		self.assertGreater(total, flt(net), "sales must carry the tax")
		self.assertAlmostEqual(total, flt(net) + flt(tax), places=2)

	def test_the_collection_total_matches_the_receipts(self):
		_columns, data = self._run()
		expected = frappe.db.sql(
			"""select sum(base_paid_amount) from `tabPayment Entry`
			where docstatus = 1 and company = %s and payment_type = 'Receive'
			  and party_type = 'Customer' and posting_date between %s and %s""",
			(self.company, add_days(today(), -365), today()),
		)[0][0]
		self.assertAlmostEqual(sum(flt(r["collection"]) for r in data), flt(expected or 0), places=2)

	def test_balance_is_sales_less_collection_on_every_row(self):
		_columns, data = self._run()
		for row in data:
			self.assertAlmostEqual(flt(row["balance"]), flt(row["sales"]) - flt(row["collection"]), places=2)

	def test_grouping_by_brand_totals_the_lines(self):
		"""A brand row sums its own lines, tax included.

		It cannot carry what sits on the invoice rather than on a line --
		freight belongs to no brand -- so it ties to the invoice total
		rather than the grand total.
		"""
		_columns, by_brand = self._run(group_by="Brand")
		expected = frappe.db.sql(
			"""select sum(sii.base_amount) from `tabSales Invoice Item` sii
			join `tabSales Invoice` si on si.name = sii.parent
			where si.docstatus = 1 and si.company = %s and si.posting_date between %s and %s""",
			(self.company, add_days(today(), -365), today()),
		)[0][0]
		self.assertAlmostEqual(sum(flt(r["sales"]) for r in by_brand), flt(expected), places=2)

	def test_brand_and_person_differ_only_by_the_invoice_level_charges(self):
		_columns, by_person = self._run()
		_columns, by_brand = self._run(group_by="Brand")
		charges = frappe.db.sql(
			"""select sum(base_grand_total - base_total) from `tabSales Invoice`
			where docstatus = 1 and company = %s and posting_date between %s and %s""",
			(self.company, add_days(today(), -365), today()),
		)[0][0]
		self.assertAlmostEqual(
			sum(flt(r["sales"]) for r in by_person) - sum(flt(r["sales"]) for r in by_brand),
			flt(charges or 0),
			places=2,
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
			"Sales Invoice",
			{"docstatus": 1, "company": self.company, "custom_sales_person": ["not in", ["", None]]},
			"custom_sales_person",
		)
		if not person:
			self.skipTest("no invoice carries a sales person")
		_columns, data = self._run(sales_person=person)
		self.assertTrue(all(r["group_value"] == person for r in data))


class TestTheOpeningIsExcluded(SummaryCase):
	"""Provable without any invoices on the site: the condition has to be in
	the SQL of both sales queries. They are built separately, so one can be
	changed without the other, and a salesman's inherited ledger would quietly
	come back as his selling."""

	def _sql_of(self, group_by):
		seen = []

		def capture(query, *args, **kwargs):
			seen.append(query)
			return []

		filters = frappe._dict(
			{
				"company": self.company,
				"from_date": add_days(today(), -365),
				"to_date": today(),
				"group_by": group_by,
			}
		)
		with patch.object(frappe.db, "sql", side_effect=capture):
			report._sales(filters)
			if group_by not in SALES_ONLY:  # the invoice total has no brand to group by
				report._invoice_totals(filters)
		return seen

	def test_both_sales_queries_leave_the_opening_out(self):
		queries = self._sql_of("Sales Person")
		self.assertEqual(len(queries), 2, "expected the line query and the invoice query")
		for query in queries:
			self.assertIn(NOT_AN_OPENING, query)

	def test_the_brand_grouping_leaves_it_out_too(self):
		queries = self._sql_of("Brand")
		self.assertEqual(len(queries), 1, "brand has only the line query")
		self.assertIn(NOT_AN_OPENING, queries[0])

	def test_collection_is_not_touched_by_it(self):
		"""Money received is a Payment Entry; it has no opening flag to read."""
		seen = []

		def capture(query, *args, **kwargs):
			seen.append(query)
			return []

		filters = frappe._dict(
			{
				"company": self.company,
				"from_date": add_days(today(), -365),
				"to_date": today(),
				"group_by": "Sales Person",
			}
		)
		with patch.object(frappe.db, "sql", side_effect=capture):
			report._collection(filters)
		self.assertTrue(seen)
		for query in seen:
			self.assertNotIn("is_opening", query)
