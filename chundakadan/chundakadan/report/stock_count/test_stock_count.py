import os

import frappe
from frappe.modules.import_file import import_file_by_path
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate

from chundakadan.chundakadan.report.stock_count.stock_count import execute

COMPANY = "Chundakadan Agencies"


class TestStockCount(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# the sample has to be something that actually holds stock, so the
		# Bin -- the truth this report is checked against -- exists for it
		row = frappe.db.sql(
			"""select sle.posting_date, sle.item_code, sle.warehouse
			from `tabStock Ledger Entry` sle
			join `tabBin` b on b.item_code = sle.item_code and b.warehouse = sle.warehouse
			where sle.is_cancelled = 0 and sle.company = %s and b.actual_qty <> 0
			order by sle.posting_date desc limit 1""",
			COMPANY,
			as_dict=True,
		)
		if not row:
			self.skipTest("no stock on this site")
		self.sample = row[0]
		self.to_date = self.sample.posting_date
		self.from_date = add_days(self.to_date, -30)

	def _run(self, **extra):
		filters = {"company": COMPANY, "from_date": self.from_date, "to_date": self.to_date}
		filters.update(extra)
		return execute(filters)

	def _ledger(self, sql, args):
		return frappe.db.sql(sql, args, as_dict=True)[0]

	def test_columns(self):
		columns, _data = self._run()
		names = [c["fieldname"] for c in columns]
		for field in (
			"item_code", "item_name", "brand", "item_group", "warehouse",
			"balance_qty", "uom", "stock_value", "in_qty", "out_qty",
		):
			self.assertIn(field, names)

	def test_balance_is_the_closing_stock_as_on_to_date(self):
		# the Bin is the truth. Summing actual_qty is NOT: a Stock
		# Reconciliation writes actual_qty = 0 and puts the balance in
		# qty_after_transaction, so a sum reads zero for reconciled stock.
		expected = self._ledger(
			"""select coalesce(sum(actual_qty), 0) as qty, coalesce(sum(stock_value), 0) as value
			from `tabBin` where item_code = %(item)s and warehouse = %(wh)s""",
			{"company": COMPANY, "item": self.sample.item_code, "wh": self.sample.warehouse, "to_date": self.to_date},
		)
		_columns, data = self._run(item_code=self.sample.item_code, hide_zero_balance=0)
		row = next(r for r in data if r.warehouse == self.sample.warehouse)
		self.assertAlmostEqual(flt(row.balance_qty), flt(expected.qty), places=3)
		self.assertAlmostEqual(flt(row.stock_value), flt(expected.value), places=2)

	def test_balance_ignores_the_from_date(self):
		_c, wide = self._run(item_code=self.sample.item_code, hide_zero_balance=0)
		_c, narrow = self._run(
			from_date=self.to_date, item_code=self.sample.item_code, hide_zero_balance=0
		)

		def balances(rows):
			return {(r.item_code, r.get("warehouse")): flt(r.balance_qty) for r in rows}

		self.assertEqual(balances(wide), balances(narrow))

	def test_in_and_out_cover_only_the_date_range(self):
		"""Movement is the change in balance, so a reconciliation counts too."""
		_columns, data = self._run(item_code=self.sample.item_code, hide_zero_balance=0)
		row = next(r for r in data if r.warehouse == self.sample.warehouse)
		self.assertGreaterEqual(flt(row.in_qty), 0)
		self.assertGreaterEqual(flt(row.out_qty), 0)

		opening = self._ledger(
			"""select qty_after_transaction as qty from `tabStock Ledger Entry`
			where is_cancelled = 0 and item_code = %(item)s and warehouse = %(wh)s
			  and posting_date < %(from_date)s
			order by posting_date desc, posting_time desc, creation desc limit 1""",
			{"item": self.sample.item_code, "wh": self.sample.warehouse, "from_date": self.from_date},
		) if frappe.db.exists(
			"Stock Ledger Entry",
			{"item_code": self.sample.item_code, "warehouse": self.sample.warehouse,
			 "posting_date": ["<", self.from_date], "is_cancelled": 0},
		) else frappe._dict({"qty": 0})
		self.assertAlmostEqual(
			flt(opening.qty) + flt(row.in_qty) - flt(row.out_qty),
			flt(row.balance_qty),
			places=3,
			msg="opening + in - out must land on the closing balance",
		)

	def test_stock_set_by_a_reconciliation_is_not_reported_as_zero(self):
		"""The bug this report shipped with: a Stock Reconciliation writes
		actual_qty = 0, so sum(actual_qty) read zero for the whole site."""
		row = frappe.db.sql(
			"""select b.item_code, b.warehouse, b.actual_qty from `tabBin` b
			join `tabStock Ledger Entry` sle on sle.item_code = b.item_code
			 and sle.warehouse = b.warehouse and sle.voucher_type = 'Stock Reconciliation'
			 and sle.is_cancelled = 0
			where b.actual_qty > 0
			  and (select coalesce(sum(s2.actual_qty), 0) from `tabStock Ledger Entry` s2
			       where s2.is_cancelled = 0 and s2.item_code = b.item_code
			         and s2.warehouse = b.warehouse) <> b.actual_qty
			limit 1""",
			as_dict=True,
		)
		if not row:
			self.skipTest("no reconciliation-set stock on this site")
		sample = row[0]
		_columns, data = execute({
			"company": COMPANY, "from_date": self.from_date, "to_date": self.to_date,
			"item_code": sample.item_code, "hide_zero_balance": 0,
		})
		reported = next(r for r in data if r.warehouse == sample.warehouse)
		self.assertAlmostEqual(flt(reported.balance_qty), flt(sample.actual_qty), places=3)
		self.assertNotEqual(flt(reported.balance_qty), 0.0)

	def test_one_row_per_item_and_warehouse(self):
		_columns, data = self._run(hide_zero_balance=0)
		keys = [(r.item_code, r.warehouse) for r in data]
		self.assertEqual(len(keys), len(set(keys)))

	def test_warehouse_filter(self):
		_columns, data = self._run(warehouse=self.sample.warehouse, hide_zero_balance=0)
		self.assertTrue(data)
		self.assertTrue(all(r.warehouse == self.sample.warehouse for r in data))

	def test_item_details_come_from_the_item_master(self):
		item = frappe.db.get_value(
			"Item", self.sample.item_code, ["item_name", "brand", "item_group", "stock_uom"], as_dict=True
		)
		_columns, data = self._run(item_code=self.sample.item_code, hide_zero_balance=0)
		row = data[0]
		self.assertEqual(
			(row.item_name, row.brand, row.item_group, row.uom),
			(item.item_name, item.brand, item.item_group, item.stock_uom),
		)

	def test_item_group_filter(self):
		group = frappe.db.get_value("Item", self.sample.item_code, "item_group")
		_columns, data = self._run(item_group=group, hide_zero_balance=0)
		self.assertTrue(data)
		self.assertTrue(all(r.item_group == group for r in data))

	def test_brand_filter(self):
		brand = frappe.db.get_value("Item", self.sample.item_code, "brand")
		if not brand:
			self.skipTest("sample item has no brand")
		_columns, data = self._run(brand=brand, hide_zero_balance=0)
		self.assertTrue(data)
		self.assertTrue(all(r.brand == brand for r in data))

	def test_hide_zero_balance_drops_only_the_empty_rows(self):
		_columns, all_rows = self._run(hide_zero_balance=0)
		_columns, kept = self._run(hide_zero_balance=1)
		self.assertTrue(all(flt(r.balance_qty) for r in kept))
		zeros = [r for r in all_rows if not flt(r.balance_qty)]
		self.assertEqual(len(all_rows) - len(zeros), len(kept))

	def test_a_date_before_any_stock_moved_is_empty(self):
		first = frappe.db.sql(
			"select min(posting_date) from `tabStock Ledger Entry` where is_cancelled = 0 and company = %s",
			COMPANY,
		)[0][0]
		day = add_days(first, -1)
		_columns, data = execute({"company": COMPANY, "from_date": day, "to_date": day})
		self.assertEqual(data, [])

	def test_missing_filters_and_reversed_range(self):
		with self.assertRaises(frappe.ValidationError):
			execute({"from_date": self.from_date, "to_date": self.to_date})
		with self.assertRaises(frappe.ValidationError):
			execute({"company": COMPANY})
		with self.assertRaises(frappe.ValidationError):
			execute({"company": COMPANY, "from_date": getdate("2026-09-10"), "to_date": getdate("2026-09-01")})

	def test_roles_can_open_it(self):
		import_file_by_path(
			os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_count.json"), force=True
		)
		report = frappe.get_doc("Report", "Stock Count")
		self.assertEqual(report.ref_doctype, "Stock Ledger Entry")
		self.assertTrue({"Stock User", "Stock Manager", "Accounts User"}.issubset({r.role for r in report.roles}))
		email = "stock.count.user@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": "Stock Count",
				"send_welcome_email": 0, "user_type": "System User",
			}).insert()
		frappe.get_doc("User", email).add_roles("Stock User")
		frappe.set_user(email)
		try:
			self.assertTrue(report.is_permitted())
			self.assertTrue(frappe.has_permission(report.ref_doctype, "report"))
		finally:
			frappe.set_user("Administrator")
		frappe.db.rollback()


class TestStockCountGroupByItem(TestStockCount):
	"""Group By = Item collapses the warehouses into one row per item."""

	def _run(self, **extra):
		filters = {
			"company": COMPANY, "from_date": self.from_date, "to_date": self.to_date,
			"group_by": "Item",
		}
		filters.update(extra)
		return execute(filters)

	def test_columns(self):
		columns, _data = self._run()
		names = [c["fieldname"] for c in columns]
		self.assertNotIn("warehouse", names)
		for field in ("item_code", "item_name", "brand", "item_group", "balance_qty", "uom", "stock_value"):
			self.assertIn(field, names)

	def test_stock_set_by_a_reconciliation_is_not_reported_as_zero(self):
		"""The bug this report shipped with: a Stock Reconciliation writes
		actual_qty = 0, so sum(actual_qty) read zero for the whole site."""
		row = frappe.db.sql(
			"""select b.item_code, b.warehouse, b.actual_qty from `tabBin` b
			join `tabStock Ledger Entry` sle on sle.item_code = b.item_code
			 and sle.warehouse = b.warehouse and sle.voucher_type = 'Stock Reconciliation'
			 and sle.is_cancelled = 0
			where b.actual_qty > 0
			  and (select coalesce(sum(s2.actual_qty), 0) from `tabStock Ledger Entry` s2
			       where s2.is_cancelled = 0 and s2.item_code = b.item_code
			         and s2.warehouse = b.warehouse) <> b.actual_qty
			limit 1""",
			as_dict=True,
		)
		if not row:
			self.skipTest("no reconciliation-set stock on this site")
		sample = row[0]
		_columns, data = execute({
			"company": COMPANY, "from_date": self.from_date, "to_date": self.to_date,
			"item_code": sample.item_code, "hide_zero_balance": 0,
		})
		reported = next(r for r in data if r.warehouse == sample.warehouse)
		self.assertAlmostEqual(flt(reported.balance_qty), flt(sample.actual_qty), places=3)
		self.assertNotEqual(flt(reported.balance_qty), 0.0)

	def test_one_row_per_item_and_warehouse(self):
		_columns, data = self._run(hide_zero_balance=0)
		codes = [r.item_code for r in data]
		self.assertEqual(len(codes), len(set(codes)))

	def test_warehouse_filter(self):
		_columns, data = self._run(warehouse=self.sample.warehouse, hide_zero_balance=0)
		self.assertTrue(data)
		self.assertNotIn("warehouse", data[0])

	def test_balance_is_the_closing_stock_as_on_to_date(self):
		expected = self._ledger(
			"""select coalesce(sum(actual_qty), 0) as qty, coalesce(sum(stock_value), 0) as value
			from `tabBin` where item_code = %(item)s""",
			{"company": COMPANY, "item": self.sample.item_code, "to_date": self.to_date},
		)
		_columns, data = self._run(item_code=self.sample.item_code, hide_zero_balance=0)
		self.assertEqual(len(data), 1)
		self.assertAlmostEqual(flt(data[0].balance_qty), flt(expected.qty), places=3)
		self.assertAlmostEqual(flt(data[0].stock_value), flt(expected.value), places=2)

	def test_in_and_out_cover_only_the_date_range(self):
		_columns, data = self._run(item_code=self.sample.item_code, hide_zero_balance=0)
		self.assertGreaterEqual(flt(data[0].in_qty), 0)
		self.assertGreaterEqual(flt(data[0].out_qty), 0)

	def test_it_is_the_warehouse_rows_added_up(self):
		"""Item rows must total exactly what the warehouse-wise rows total."""
		_columns, per_warehouse = execute({
			"company": COMPANY, "from_date": self.from_date, "to_date": self.to_date, "hide_zero_balance": 0,
		})
		_columns, per_item = self._run(hide_zero_balance=0)
		wanted = {}
		for row in per_warehouse:
			wanted[row.item_code] = wanted.get(row.item_code, 0) + flt(row.balance_qty)
		self.assertEqual(len(per_item), len({r.item_code for r in per_warehouse}))
		for row in per_item:
			self.assertAlmostEqual(flt(row.balance_qty), wanted[row.item_code], places=3, msg=row.item_code)
