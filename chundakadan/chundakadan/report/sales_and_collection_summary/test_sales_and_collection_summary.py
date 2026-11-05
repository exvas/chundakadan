from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate, today

from chundakadan.chundakadan.report.sales_and_collection_summary import sales_and_collection_summary as report
from chundakadan.chundakadan.report.sales_and_collection_summary.sales_and_collection_summary import (
	GROUPS,
	NOT_AN_OPENING,
	SALES_ONLY,
	execute,
	get_columns,
)
from chundakadan.testing import a_customer

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


class TestCollectionDetail(SummaryCase):
	"""The list behind the Collection figure.

	The office checks an executive's collection by reading the receipts that
	make it up, so the two have to agree to the rupee -- a list that does not
	add up to the figure it sits under is worse than no list. The case builds
	its own receipts: a bench with no Payment Entry on it would otherwise skip
	every assertion here and prove nothing.
	"""

	def setUp(self):
		super().setUp()
		self.customer = a_customer(self.company)
		self.receivable = frappe.get_cached_value("Company", self.company, "default_receivable_account")
		self.bank = frappe.db.get_value(
			"Account",
			{"company": self.company, "is_group": 0, "account_type": ["in", ["Bank", "Cash"]]},
			"name",
			order_by="name asc",
		)
		if not (self.customer and self.receivable and self.bank):
			self.skipTest("this bench cannot build a Payment Entry")
		self._clear_previous()
		self.people = self._two_sales_people()
		self.paid = {
			self.people[0]: 1500,
			self.people[1]: 2500,
		}
		self.day = add_days(today(), -2)
		self._receipt(self.people[0], 1000)
		self._receipt(self.people[0], 500)
		self._receipt(self.people[1], 2500)

	def _clear_previous(self):
		"""A submitted receipt outlives the per-test rollback, so by the
		tenth test the same two people had ten times the money. Every test
		starts with only the receipts it made itself."""
		names = frappe.get_all("Payment Entry", filters={"party": self.customer}, pluck="name")
		if not names:
			return
		frappe.db.delete("GL Entry", {"voucher_type": "Payment Entry", "voucher_no": ["in", names]})
		frappe.db.delete("Payment Entry", {"name": ["in", names]})

	def _two_sales_people(self):
		names = frappe.get_all("Sales Person", filters={"enabled": 1}, pluck="name", order_by="name asc")
		names = [n for n in names if n][:2]
		while len(names) < 2:
			doc = frappe.get_doc(
				{
					"doctype": "Sales Person",
					"sales_person_name": f"_Test Collection Person {len(names)}",
					"is_group": 0,
				}
			)
			doc.flags.ignore_mandatory = True
			doc.insert(ignore_permissions=True)
			names.append(doc.name)
		return names

	def _receipt(self, sales_person, amount):
		doc = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": "Receive",
				"company": self.company,
				"posting_date": add_days(today(), -2),
				"party_type": "Customer",
				"party": self.customer,
				"paid_from": self.receivable,
				"paid_to": self.bank,
				"paid_amount": amount,
				"received_amount": amount,
				"source_exchange_rate": 1,
				"target_exchange_rate": 1,
				"reference_no": frappe.generate_hash(length=6),
				"reference_date": add_days(today(), -2),
				"custom_sales_person": sales_person,
			}
		)
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		doc.submit()
		# the sales person default fills this from the customer when it is
		# blank; it must not overwrite one that was given
		self.assertEqual(doc.custom_sales_person, sales_person)
		return doc

	def _detail(self, **extra):
		return self._run(group_by="Sales Person", collection_detail=1, **extra)[1]

	def _mine(self, rows):
		return [r for r in rows if r["sales_person"] in self.paid]

	def test_one_row_per_receipt(self):
		self.assertEqual(len(self._mine(self._detail())), 3)

	def test_the_rows_add_up_to_the_summary_figure(self):
		summary = {r["group_value"]: r["collection"] for r in self._run(group_by="Sales Person")[1]}
		per_person = {}
		for row in self._mine(self._detail()):
			per_person[row["sales_person"]] = per_person.get(row["sales_person"], 0) + row["amount"]
		self.assertEqual({k: flt(v, 2) for k, v in per_person.items()}, self.paid)
		for person, amount in self.paid.items():
			self.assertEqual(flt(summary[person], 2), amount, person)

	def test_it_carries_what_somebody_verifying_needs(self):
		row = self._mine(self._detail())[0]
		for field in ("posting_date", "sales_person", "customer", "customer_name", "amount"):
			self.assertIsNotNone(row.get(field), field)
		self.assertEqual(row["customer"], self.customer)
		self.assertEqual(getdate(row["posting_date"]), getdate(self.day))

	def test_the_sales_person_filter_narrows_it(self):
		person = self.people[0]
		rows = self._detail(sales_person=person)
		self.assertEqual({r["sales_person"] for r in rows}, {person})
		self.assertEqual(flt(sum(r["amount"] for r in rows), 2), self.paid[person])

	def test_the_customer_filter_narrows_it(self):
		rows = self._detail(customer=self.customer)
		self.assertTrue(rows)
		self.assertEqual({r["customer"] for r in rows}, {self.customer})

	def test_a_draft_receipt_is_not_listed(self):
		draft = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": "Receive",
				"company": self.company,
				"posting_date": add_days(today(), -2),
				"party_type": "Customer",
				"party": self.customer,
				"paid_from": self.receivable,
				"paid_to": self.bank,
				"paid_amount": 9999,
				"received_amount": 9999,
				"source_exchange_rate": 1,
				"target_exchange_rate": 1,
				"custom_sales_person": self.people[0],
			}
		)
		draft.flags.ignore_mandatory = True
		draft.insert(ignore_permissions=True)
		self.assertNotIn(draft.name, [r["payment_entry"] for r in self._detail()])

	def test_a_receipt_outside_the_period_is_not_listed(self):
		rows = self._run(
			group_by="Sales Person",
			collection_detail=1,
			from_date=today(),
			to_date=today(),
		)[1]
		self.assertEqual(self._mine(rows), [])

	def test_the_columns_change_with_the_tick(self):
		detail_columns = [c["fieldname"] for c in self._run(group_by="Sales Person", collection_detail=1)[0]]
		self.assertIn("payment_entry", detail_columns)
		self.assertNotIn("sales", detail_columns)
		summary_columns = [c["fieldname"] for c in self._run(group_by="Sales Person")[0]]
		self.assertIn("sales", summary_columns)
		self.assertNotIn("payment_entry", summary_columns)

	def test_brand_says_why_there_is_no_detail(self):
		"""A payment is not against a line, so it has no brand. Handing back
		the summary without a word would look like the tick did nothing."""
		result = self._run(group_by="Brand", collection_detail=1)
		self.assertEqual(len(result), 3, "expected columns, data and a message")
		self.assertIn("brand", result[2].lower())
		self.assertNotIn("payment_entry", [c["fieldname"] for c in result[0]])

	def test_the_detail_and_the_summary_read_the_same_receipts(self):
		"""Both go through _collection_conditions, so neither can quietly
		start counting a different set."""
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
			report._collection_detail(filters)
		self.assertEqual(len(seen), 2)
		for condition in report._collection_conditions(filters):
			for query in seen:
				self.assertIn(condition, query)
