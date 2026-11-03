"""The Late Entry Details table must stay removable, never hand-editable."""

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events.item_brand import ensure_item_brand_mandatory
from chundakadan.install import before_tests, ensure_additional_salary_fields

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


class TestBeforeTestsRelaxesMandatoryFields(FrappeTestCase):
	"""`bench run-tests` builds ERPNext's own `_Test Item` before a single test
	runs, and that record carries no brand. With brand mandatory the whole suite
	dies at bootstrap — not one test fails, none of them get to run — so
	before_tests has to stand the flag down for the test bench.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls._commit = frappe.db.commit
		frappe.db.commit = lambda *a, **k: None

	@classmethod
	def tearDownClass(cls):
		frappe.db.commit = cls._commit
		super().tearDownClass()

	def test_item_brand_is_stood_down(self):
		ensure_item_brand_mandatory()
		frappe.clear_cache(doctype="Item")
		self.assertTrue(
			frappe.get_meta("Item", cached=False).get_field("brand").reqd,
			"the live rule has to be in place for this test to mean anything",
		)

		before_tests()

		self.assertFalse(
			frappe.get_meta("Item", cached=False).get_field("brand").reqd,
			"brand left mandatory: `_Test Item` cannot be created and every " "test module dies at bootstrap",
		)

	def test_the_employee_fields_are_stood_down_too(self):
		before_tests()

		for fieldname in ("designation", "holiday_list", "department", "user_id"):
			self.assertFalse(
				frappe.get_meta("Employee", cached=False).get_field(fieldname).reqd,
				f"Employee.{fieldname} left mandatory: HRMS's `_T-Employee-00001` cannot be created",
			)

	def test_nothing_is_left_mandatory_by_a_custom_field_or_setter(self):
		"""The sweep, not a list of names: the next field someone ticks
		"Mandatory" in Customize Form must not take the suite down with it.
		"""
		before_tests()

		self.assertEqual(
			frappe.get_all("Property Setter", filters={"property": "reqd", "value": "1"}, pluck="name"),
			[],
			"a Property Setter still promotes a field to mandatory",
		)
		self.assertEqual(
			frappe.get_all("Custom Field", filters={"reqd": 1}, pluck="name"),
			[],
			"a Custom Field is still mandatory",
		)
