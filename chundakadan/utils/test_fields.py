import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.utils.fields import field_changed


class TestFieldChanged(FrappeTestCase):
	"""The comparison that decides whether a guard refuses an edit.

	Written after an accountant could not correct a valuation rate on an
	approved Item: Approved On "changed" because a form hands a Datetime
	back as a string.
	"""

	def _pair(self, new, old):
		return frappe._dict({"custom_approved_on": new}), frappe._dict({"custom_approved_on": old})

	def test_a_datetime_and_its_own_string_are_the_same(self):
		from frappe.utils import get_datetime

		stamp = get_datetime("2026-10-05 10:00:00")
		doc, before = self._pair(str(stamp), stamp)
		self.assertFalse(field_changed("Item", doc, before, "custom_approved_on"))

	def test_a_different_datetime_is_a_change(self):
		doc, before = self._pair("2020-01-01 00:00:00", "2026-10-05 10:00:00")
		self.assertTrue(field_changed("Item", doc, before, "custom_approved_on"))

	def test_none_and_empty_string_are_the_same_emptiness(self):
		doc = frappe._dict({"custom_rejection_reason": ""})
		before = frappe._dict({"custom_rejection_reason": None})
		self.assertFalse(field_changed("Item", doc, before, "custom_rejection_reason"))

	def test_text_still_compares(self):
		doc = frappe._dict({"custom_rejection_reason": "wrong rate"})
		before = frappe._dict({"custom_rejection_reason": None})
		self.assertTrue(field_changed("Item", doc, before, "custom_rejection_reason"))

	def test_a_float_and_its_string_are_the_same(self):
		doc = frappe._dict({"valuation_rate": "123.45"})
		before = frappe._dict({"valuation_rate": 123.45})
		self.assertFalse(field_changed("Item", doc, before, "valuation_rate"))

	def test_a_real_float_change_is_caught(self):
		doc = frappe._dict({"valuation_rate": 123.46})
		before = frappe._dict({"valuation_rate": 123.45})
		self.assertTrue(field_changed("Item", doc, before, "valuation_rate"))

	def test_a_check_reads_the_same_as_its_int(self):
		doc = frappe._dict({"disabled": "1"})
		before = frappe._dict({"disabled": 1})
		self.assertFalse(field_changed("Item", doc, before, "disabled"))

	def test_an_unknown_field_falls_back_to_text(self):
		doc = frappe._dict({"not_a_field": "a"})
		before = frappe._dict({"not_a_field": "a"})
		self.assertFalse(field_changed("Item", doc, before, "not_a_field"))

	def test_an_unparseable_date_is_treated_as_a_change(self):
		doc = frappe._dict({"custom_approved_on": "not a date"})
		before = frappe._dict({"custom_approved_on": "2026-10-05 10:00:00"})
		self.assertTrue(field_changed("Item", doc, before, "custom_approved_on"))
