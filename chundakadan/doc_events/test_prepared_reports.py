"""Reports must open directly, never as background (Prepared) reports."""

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events.prepared_reports import ensure_prepared_reports_disabled

test_ignore = ["Report"]


class TestPreparedReports(FrappeTestCase):
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

	def _sample(self):
		return frappe.db.get_value("Report", {"report_type": "Script Report"}, "name")

	def test_clears_the_flag_and_stops_the_automation(self):
		name = self._sample()
		frappe.db.set_value(
			"Report",
			name,
			{"prepared_report": 1, "disable_prepared_report_automation": 0},
			update_modified=False,
		)
		changed = ensure_prepared_reports_disabled()
		self.assertGreaterEqual(changed, 1)
		row = frappe.db.get_value(
			"Report", name, ["prepared_report", "disable_prepared_report_automation"], as_dict=True
		)
		self.assertEqual(row.prepared_report, 0)
		self.assertEqual(row.disable_prepared_report_automation, 1)

	def test_fixes_a_report_where_only_the_automation_is_on(self):
		name = self._sample()
		ensure_prepared_reports_disabled()
		frappe.db.set_value("Report", name, "disable_prepared_report_automation", 0, update_modified=False)
		self.assertEqual(ensure_prepared_reports_disabled(), 1)

	def test_is_idempotent(self):
		ensure_prepared_reports_disabled()
		self.assertEqual(ensure_prepared_reports_disabled(), 0)

	def test_no_report_is_left_in_background_mode(self):
		ensure_prepared_reports_disabled()
		self.assertEqual(frappe.db.count("Report", {"prepared_report": 1}), 0)
		self.assertEqual(
			frappe.db.count("Report", {"disable_prepared_report_automation": 0}), 0
		)
