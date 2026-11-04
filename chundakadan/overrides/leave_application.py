import frappe
from hrms.hr.doctype.leave_application.leave_application import LeaveApplication

from chundakadan.doc_events.leave_status import CHAIN_STATUSES


class CustomLeaveApplication(LeaveApplication):
	def validate(self):
		super().validate()

		self.sync_custom_status()

	def on_update(self):
		super().on_update()

		self.sync_custom_status()

	def before_update_after_submit(self):
		# validate() does not run when a submitted leave is saved, so keep
		# status in step with custom_approval_status here as well.
		self.sync_custom_status()

	def _validate_update_after_submit(self):
		# status mirrors custom_approval_status (allow_on_submit) and is set by
		# the approval flow on already-submitted leaves. HRMS ships status with
		# allow_on_submit=0, so let status change after submit here in code
		# instead of relying on a Property Setter that may not exist on a site.
		# Every other field is still checked by the standard validation.
		new_status = self.status
		self.status = frappe.db.get_value(self.doctype, self.name, "status")
		try:
			super()._validate_update_after_submit()
		finally:
			self.status = new_status

	def sync_custom_status(self):
		# CHAIN_STATUSES lives beside the Property Setter that widens the
		# status field to hold these, so the two cannot drift apart again.
		if self.custom_approval_status in CHAIN_STATUSES:
			self.status = CHAIN_STATUSES[self.custom_approval_status]
