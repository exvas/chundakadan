"""A log call in a failure path must not be able to fail the request."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.utils.errors import TITLE_LENGTH, log_failure


class TestLogFailure(FrappeTestCase):
	def _latest(self):
		return frappe.db.get_value("Error Log", {}, ["method", "error"], order_by="creation desc")

	def test_the_detail_goes_in_the_body_not_the_title(self):
		log_failure("Approval email not sent", "Leave Application LAP-1 → somebody: no account")
		title, error = self._latest()
		self.assertEqual(title, "Approval email not sent")
		self.assertIn("LAP-1", error)

	def test_a_title_that_is_too_long_is_cut_not_refused(self):
		log_failure("t" * 500, "detail")
		title, _error = self._latest()
		self.assertEqual(len(title), TITLE_LENGTH)

	def test_it_never_raises_even_when_the_log_itself_fails(self):
		with patch.object(frappe, "log_error", side_effect=RuntimeError("the log is down")):
			log_failure("anything", "at all")  # must not raise

	def test_it_carries_the_traceback_of_what_went_wrong(self):
		try:
			raise ValueError("the real cause")
		except ValueError:
			log_failure("Something failed")
		_title, error = self._latest()
		self.assertIn("the real cause", error)
