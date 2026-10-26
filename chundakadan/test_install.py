"""The Late Entry Details table must stay removable, never hand-editable."""

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.install import ensure_additional_salary_fields

TABLE_FIELD = "Additional Salary-custom_late_entry_details"


class TestLateEntryTable(FrappeTestCase):
	def test_the_table_is_editable_so_a_day_can_be_dropped(self):
		ensure_additional_salary_fields()
		self.assertEqual(frappe.db.get_value("Custom Field", TABLE_FIELD, "read_only"), 0)

	def test_a_table_left_read_only_is_healed_on_migrate(self):
		"""The field shipped read-only; migrate has to undo that on live sites."""
		frappe.db.set_value("Custom Field", TABLE_FIELD, "read_only", 1)
		self.assertEqual(frappe.db.get_value("Custom Field", TABLE_FIELD, "read_only"), 1)

		ensure_additional_salary_fields()

		self.assertEqual(
			frappe.db.get_value("Custom Field", TABLE_FIELD, "read_only"),
			0,
			"a site that already has the read-only field must be healed, "
			"otherwise HR still cannot remove a day",
		)

	def test_every_column_is_read_only_so_figures_cannot_be_typed_in(self):
		meta = frappe.get_meta("Late Entry Detail")
		typeable = [f.fieldname for f in meta.fields if not f.read_only]
		self.assertEqual(
			typeable,
			[],
			"a column anyone can type into lets the deduction be rewritten by hand",
		)
