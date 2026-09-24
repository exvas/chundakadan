import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from chundakadan.doc_events.purchase_invoice_available_qty import (
	FIELD,
	GRID_COLUMNS,
	available_qty,
	ensure_purchase_invoice_available_qty,
	set_available_qty,
	warehouse_for,
)

DOCTYPE = "Purchase Invoice Item"


class AvailableQtyCase(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		ensure_purchase_invoice_available_qty()
		row = frappe.db.sql(
			"""select item_code, warehouse, actual_qty from `tabBin`
			where actual_qty > 0 order by actual_qty desc limit 1""",
			as_dict=True,
		)
		if not row:
			self.skipTest("no stock on this site")
		self.bin = row[0]


class TestTheColumn(AvailableQtyCase):
	def test_the_field_exists_and_is_read_only(self):
		field = frappe.get_meta(DOCTYPE).get_field(FIELD)
		self.assertIsNotNone(field)
		self.assertEqual(field.label, "Avail. Qty")
		self.assertEqual(field.fieldtype, "Float")
		self.assertEqual(field.read_only, 1)
		self.assertEqual(field.in_list_view, 1)

	def test_it_sits_right_after_the_accepted_quantity(self):
		fields = [f.fieldname for f in frappe.get_meta(DOCTYPE).fields]
		self.assertEqual(fields[fields.index("qty") + 1], FIELD)

	def test_the_grid_still_adds_up_to_ten(self):
		meta = frappe.get_meta(DOCTYPE)
		width = sum(
			(f.columns or 0) for f in meta.fields if f.in_list_view and (f.columns or 0)
		)
		self.assertLessEqual(width, 10, "the grid is ten columns wide")

	def test_rate_gave_a_column_up(self):
		self.assertEqual(frappe.get_meta(DOCTYPE).get_field("rate").columns, GRID_COLUMNS["rate"])

	def test_running_it_twice_changes_nothing(self):
		ensure_purchase_invoice_available_qty()
		field = frappe.get_meta(DOCTYPE).get_field(FIELD)
		self.assertEqual(field.label, "Avail. Qty")


class TestTheNumber(AvailableQtyCase):
	def test_it_reads_the_bin_for_that_warehouse(self):
		self.assertAlmostEqual(
			available_qty(self.bin.item_code, self.bin.warehouse),
			flt(self.bin.actual_qty),
			places=3,
		)

	def test_an_item_with_no_bin_there_is_zero(self):
		self.assertEqual(available_qty(self.bin.item_code, "No Such Warehouse - XX"), 0.0)

	def test_missing_arguments_are_zero_not_an_error(self):
		self.assertEqual(available_qty(None, None), 0.0)
		self.assertEqual(available_qty(self.bin.item_code, None), 0.0)
		self.assertEqual(available_qty(None, self.bin.warehouse), 0.0)

	def test_the_row_warehouse_wins_over_the_invoice_one(self):
		row = frappe._dict({"warehouse": "Row - CA"})
		self.assertEqual(warehouse_for(row, "Parent - CA"), "Row - CA")

	def test_a_row_with_no_warehouse_falls_back_to_the_invoice_one(self):
		self.assertEqual(warehouse_for(frappe._dict({"warehouse": None}), "Parent - CA"), "Parent - CA")


class TestFillingTheRows(AvailableQtyCase):
	def _invoice(self, docstatus=0, row_warehouse=None, set_warehouse=None):
		return frappe._dict({
			"docstatus": docstatus,
			"set_warehouse": set_warehouse,
			"items": [
				frappe._dict({
					"item_code": self.bin.item_code,
					"warehouse": row_warehouse,
					"set": lambda field, value, _row=None: None,
				})
			],
		})

	def _row(self, **kwargs):
		values = {}
		row = frappe._dict(kwargs)
		row.set = lambda field, value: values.__setitem__(field, value)
		row.get = lambda field, default=None: (
			values.get(field, default) if field in values else dict(kwargs).get(field, default)
		)
		return row, values

	def test_a_draft_row_gets_the_warehouse_stock(self):
		row, values = self._row(item_code=self.bin.item_code, warehouse=self.bin.warehouse)
		doc = frappe._dict({"docstatus": 0, "set_warehouse": None, "items": [row]})
		set_available_qty(doc)
		self.assertAlmostEqual(values[FIELD], flt(self.bin.actual_qty), places=3)

	def test_a_row_with_no_warehouse_uses_the_invoice_warehouse(self):
		row, values = self._row(item_code=self.bin.item_code, warehouse=None)
		doc = frappe._dict({"docstatus": 0, "set_warehouse": self.bin.warehouse, "items": [row]})
		set_available_qty(doc)
		self.assertAlmostEqual(values[FIELD], flt(self.bin.actual_qty), places=3)

	def test_a_submitted_invoice_keeps_the_figure_it_had(self):
		row, values = self._row(item_code=self.bin.item_code, warehouse=self.bin.warehouse)
		doc = frappe._dict({"docstatus": 1, "set_warehouse": None, "items": [row]})
		set_available_qty(doc)
		self.assertEqual(values, {}, "a submitted invoice must not be rewritten")

	def test_an_invoice_with_no_rows_is_fine(self):
		set_available_qty(frappe._dict({"docstatus": 0, "set_warehouse": None, "items": []}))
		set_available_qty(frappe._dict({"docstatus": 0, "set_warehouse": None}))
