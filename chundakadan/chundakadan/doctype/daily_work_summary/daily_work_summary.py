# Copyright (c) 2026, Chundakadan and contributors
"""Controller for Daily Work Summary.

The rules live in `chundakadan/chundakadan/api/work_summary.py` so the
desk, the mobile endpoints and the tests all share one implementation.
"""

from frappe.model.document import Document

from chundakadan.chundakadan.api import work_summary


class DailyWorkSummary(Document):
	def validate(self):
		work_summary.validate(self)

	def on_cancel(self):
		self.custom_approval_status = "Rejected"
		self.current_approver = None
