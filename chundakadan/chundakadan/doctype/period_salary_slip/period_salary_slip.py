# Copyright (c) 2026, Ashkar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PeriodSalarySlip(Document):
	def validate(self):
		self._validate_dates()

	def _validate_dates(self):
		if self.from_date and self.to_date:
			if self.from_date > self.to_date:
				frappe.throw(_("From Date cannot be later than To Date."))
