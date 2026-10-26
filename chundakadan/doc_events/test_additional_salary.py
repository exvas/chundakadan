"""The Amount of a late-arrival deduction is the sum of the days still listed."""

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events.additional_salary import sync_late_entry_total

FETCHED_REASON = "Late entry deduction 2026-10-01 to 2026-10-31: 204 late min over 5 day(s)"


def day(minutes, deduction):
	return frappe._dict({"late_minutes": minutes, "deduction": deduction})


def salary(rows, **kwargs):
	return frappe._dict({
		"salary_component": "Late Arrival Deduction",
		"custom_reason": FETCHED_REASON,
		"custom_late_entry_details": rows,
		"amount": 307,
		**kwargs,
	})


class TestLateEntryTotal(FrappeTestCase):
	def test_dropping_a_day_drops_its_deduction(self):
		doc = salary([day(2, 3.01), day(20, 30.07), day(36, 54.12), day(5, 7.52)])
		sync_late_entry_total(doc)
		self.assertEqual(doc.amount, 95)

	def test_the_reason_restates_what_is_left(self):
		doc = salary([day(2, 3.01), day(20, 30.07)])
		sync_late_entry_total(doc)
		self.assertIn("22 late min over 2 day(s)", doc.custom_reason)
		self.assertIn("2026-10-01 to 2026-10-31", doc.custom_reason,
					  "the period that was fetched must survive")

	def test_dropping_every_day_cuts_nothing(self):
		doc = salary([])
		sync_late_entry_total(doc)
		self.assertEqual(doc.amount, 0, "no days left means no deduction")

	def test_a_hand_written_deduction_is_left_alone(self):
		doc = salary([], custom_reason="Agreed with HR", amount=500)
		sync_late_entry_total(doc)
		self.assertEqual(doc.amount, 500)

	def test_another_component_is_never_touched(self):
		doc = salary([day(99, 999.0)], salary_component="Incentive", amount=5000)
		sync_late_entry_total(doc)
		self.assertEqual(doc.amount, 5000)

	def test_the_total_is_rounded_to_the_rupee(self):
		doc = salary([day(1, 0.4), day(1, 0.4)])
		sync_late_entry_total(doc)
		self.assertEqual(doc.amount, 1)
