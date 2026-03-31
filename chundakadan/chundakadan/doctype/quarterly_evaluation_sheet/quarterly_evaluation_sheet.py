# Copyright (c) 2026, Ashkar and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import timedelta, date
class QuarterlyEvaluationSheet(Document):
	@frappe.whitelist()
	def set_evaluation_range_date(self):
		if not self.date_of_evaluation:
			frappe.throw("Please select Date of Evaluation First")
		if self.quarter:
			fiscal_year = frappe.utils.getdate(self.date_of_evaluation).year
			start, end = get_quarter_dates(fiscal_year, int(self.quarter))
			self.evaluation_period_from = start
			self.evaluation_period_to = end
def get_quarter_dates(fiscal_year_start_year, quarter):
				"""
                fiscal_year_start_year: int (e.g., 2025 if FY is 2025–2026)
                quarter: int (1, 2, 3, or 4)
                """

				# Adjust if your fiscal year does NOT start in January
				fiscal_start_month = 1  # change if needed (e.g., 4 for April)

				# Calculate quarter start month
				start_month = fiscal_start_month + (quarter - 1) * 3

				# Handle year rollover
				start_year = fiscal_year_start_year
				if start_month > 12:
					start_month -= 12
					start_year += 1

				# Start date
				start_date = date(start_year, start_month, 1)

				# End month
				end_month = start_month + 2
				end_year = start_year
				if end_month > 12:
					end_month -= 12
					end_year += 1

				# Get last day of end month
				if end_month == 12:
					end_date = date(end_year, 12, 31)
				else:
					end_date = date(end_year, end_month + 1, 1) - timedelta(days=1)

				return start_date, end_date
