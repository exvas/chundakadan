import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events.interview_status import (
	OPTIONS,
	ensure_interview_on_hold_status,
)

test_ignore = ["Interview"]


class TestInterviewOnHoldStatus(FrappeTestCase):
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

	def test_on_hold_is_an_option(self):
		ensure_interview_on_hold_status()
		options = frappe.get_meta("Interview", cached=False).get_field("status").options.split("\n")
		self.assertIn("On Hold", options)

	def test_the_shipped_options_survive(self):
		ensure_interview_on_hold_status()
		options = frappe.get_meta("Interview", cached=False).get_field("status").options.split("\n")
		for shipped in ("Pending", "Under Review", "Cleared", "Rejected"):
			self.assertIn(shipped, options)

	def test_is_idempotent(self):
		ensure_interview_on_hold_status()
		ensure_interview_on_hold_status()
		self.assertEqual(
			frappe.db.count(
				"Property Setter",
				{"doc_type": "Interview", "field_name": "status", "property": "options"},
			),
			1,
		)

	def test_an_on_hold_interview_still_cannot_be_submitted(self):
		"""The whole point: On Hold parks the decision, it does not close it.

		HRMS allows a submit only from Cleared or Rejected.
		"""
		ensure_interview_on_hold_status()
		frappe.clear_cache(doctype="Interview")
		interview = frappe.get_doc(
			{
				"doctype": "Interview",
				"job_applicant": frappe.db.get_value("Job Applicant", {}, "name"),
				"interview_round": frappe.db.get_value("Interview Round", {}, "name"),
				"scheduled_on": frappe.utils.nowdate(),
				"from_time": "10:00:00",
				"to_time": "11:00:00",
				"status": "On Hold",
			}
		)
		interview.flags.ignore_mandatory = True
		with self.assertRaises(frappe.ValidationError):
			interview.submit()

	def test_the_option_list_is_exactly_what_we_set(self):
		ensure_interview_on_hold_status()
		self.assertEqual(
			frappe.get_meta("Interview", cached=False).get_field("status").options, OPTIONS
		)
