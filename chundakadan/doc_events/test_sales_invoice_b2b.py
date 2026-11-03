"""The B2B toggle has to be a field we ship, not one typed into the live site."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events.sales_invoice import B2B_TOGGLE, b2b_billing_enforced, ensure_b2b_toggle
from chundakadan.doc_events.stock_control import SETTINGS

FIELD = f"{SETTINGS}-{B2B_TOGGLE}"


class TestB2BToggle(FrappeTestCase):
	def test_migrate_ships_the_field(self):
		ensure_b2b_toggle()
		self.assertTrue(
			frappe.db.exists("Custom Field", FIELD),
			"without the field every Sales Invoice insert throws on a fresh bench",
		)

	def test_it_is_off_until_someone_turns_it_on(self):
		ensure_b2b_toggle()
		self.assertEqual(frappe.db.get_value("Custom Field", FIELD, "default"), "0")

	def test_reading_it_never_stops_an_invoice(self):
		"""Newer Frappe made get_single_value throw on a field that is not
		there, which is how a missing setting killed every insert."""
		with patch.object(
			frappe.db,
			"get_single_value",
			side_effect=frappe.ValidationError("Field does not exist"),
		):
			self.assertFalse(b2b_billing_enforced(), "a missing setting must read as off, not raise")

	def test_a_bench_without_the_settings_doctype_reads_as_off(self):
		with patch.object(frappe.db, "exists", return_value=False):
			self.assertFalse(b2b_billing_enforced())
