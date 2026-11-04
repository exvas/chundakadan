"""The status field must hold every status the approval chain writes."""

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events import leave_status as ls


class TestLeaveApplicationStatuses(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		ls.ensure_leave_application_statuses()

	def test_every_status_the_chain_writes_is_an_option(self):
		"""The defect this covers: three one-off patches widened the field,
		and install-app marks patches complete without running them, so on
		any site made after them the first leave the chain touched was
		refused with 'Status cannot be "Pending"'."""
		options = frappe.get_meta(ls.DOCTYPE).get_field(ls.FIELD).options.split("\n")
		for status in ls.CHAIN_STATUSES.values():
			self.assertIn(status, options, f"the chain can write {status} and the field refuses it")

	def test_hrms_own_statuses_are_still_there(self):
		options = frappe.get_meta(ls.DOCTYPE).get_field(ls.FIELD).options.split("\n")
		for status in ls.HRMS_STATUSES:
			self.assertIn(status, options)

	def test_the_override_maps_from_the_same_table_as_the_options(self):
		"""Two places disagreeing about what a status can be was the bug, so
		the override must read the mapping that ships the options."""
		from chundakadan.overrides import leave_application as override

		self.assertIs(override.CHAIN_STATUSES, ls.CHAIN_STATUSES)
		self.assertTrue(set(ls.CHAIN_STATUSES.values()) <= set(ls.status_options().split("\n")))

	def test_a_site_whose_field_was_never_widened_is_repaired(self):
		"""The actual failure: a fresh site has no such Property Setter, so
		the field carries HRMS' four options and the chain cannot write."""
		frappe.db.delete(
			"Property Setter", {"doc_type": ls.DOCTYPE, "field_name": ls.FIELD, "property": "options"}
		)
		frappe.clear_cache(doctype=ls.DOCTYPE)
		narrow = frappe.get_meta(ls.DOCTYPE).get_field(ls.FIELD).options.split("\n")
		self.assertNotIn("Pending", narrow, "this bench ships Pending, so the repair cannot be observed")

		ls.ensure_leave_application_statuses()

		widened = frappe.get_meta(ls.DOCTYPE).get_field(ls.FIELD).options.split("\n")
		self.assertIn("Pending", widened)
		self.assertIn("Partially Approved", widened)

	def test_it_is_idempotent(self):
		before = frappe.db.count("Property Setter", {"doc_type": ls.DOCTYPE, "field_name": ls.FIELD})
		ls.ensure_leave_application_statuses()
		ls.ensure_leave_application_statuses()
		self.assertEqual(
			frappe.db.count("Property Setter", {"doc_type": ls.DOCTYPE, "field_name": ls.FIELD}), before
		)
