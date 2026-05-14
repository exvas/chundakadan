# Copyright (c) 2026, Ashkar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PeriodSalarySlip(Document):
	def validate(self):
		self._validate_dates()
		self._validate_duplicate()

	def _validate_dates(self):
		if self.from_date and self.to_date:
			if self.from_date > self.to_date:
				frappe.throw(_("From Date cannot be later than To Date."))

	def _validate_duplicate(self):
		if self.employee and self.from_date and self.to_date:
			existing = frappe.db.exists(
				"Period Salary Slip",
				{
					"employee": self.employee,
					"from_date": self.from_date,
					"to_date": self.to_date,
					"name": ("!=", self.name),
				},
			)
			if existing:
				frappe.throw(
					_("A Period Salary Slip ({0}) already exists for Employee {1} between {2} and {3}.").format(
						frappe.bold(existing),
						frappe.bold(self.employee),
						frappe.bold(self.from_date),
						frappe.bold(self.to_date),
					)
				)
