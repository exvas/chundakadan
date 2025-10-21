# Copyright (c) 2025, TBO Cloud and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today, add_days, date_diff


class SalesExecutiveEmploymentAgreement(Document):
	def validate(self):
		self.validate_dates()
		self.validate_targets()
		self.update_status()
	
	def on_submit(self):
		self.status = "Active"
		self.create_performance_tracking()
	
	def on_cancel(self):
		self.status = "Cancelled"
	
	def validate_dates(self):
		"""Validate start and end dates"""
		if self.start_date and self.end_date:
			if getdate(self.end_date) < getdate(self.start_date):
				frappe.throw(_("End Date cannot be before Start Date"))
	
	def validate_targets(self):
		"""Validate performance targets"""
		if flt(self.cash_collection_amount) < 0:
			frappe.throw(_("Cash Collection Target cannot be negative"))
		
		if flt(self.sales_target_penalty_70) < 0 or flt(self.sales_target_penalty_70) > 100:
			frappe.throw(_("Sales Target Percentage must be between 0 and 100"))
		
		# Set default penalties
		if not self.cash_target_penalty:
			self.cash_target_penalty = "Failure to meet this target will result in a salary deduction, as outlined in Section 4."
		
		if not self.sales_target_penalty_below_70:
			self.sales_target_penalty_below_70 = "Failure to achieve at least 70% of the sales target will be considered unsatisfactory and may lead to corrective action or review by the Employer."
	
	def update_status(self):
		"""Update status based on dates and docstatus"""
		if self.docstatus == 0:
			self.status = "Draft"
		elif self.docstatus == 2:
			self.status = "Cancelled"
		elif self.docstatus == 1:
			if self.start_date and self.end_date:
				current_date = getdate(today())
				start = getdate(self.start_date)
				end = getdate(self.end_date)
				
				if current_date < start:
					self.status = "Active"
				elif current_date > end:
					self.status = "Completed"
				else:
					self.status = "Active"
			else:
				self.status = "Active"
	
	def create_performance_tracking(self):
		"""Create monthly performance tracking records"""
		# This can be extended to create monthly performance review documents
		pass
	
	@frappe.whitelist()
	def get_performance_summary(self, from_date=None, to_date=None):
		"""Get performance summary for the sales executive"""
		if not from_date:
			from_date = self.start_date or today()
		if not to_date:
			to_date = today()
		
		# This can be extended to fetch actual sales data
		summary = {
			"employee": self.employee_name,
			"period": f"{from_date} to {to_date}",
			"targets": {
				"cash_collection": self.cash_collection_amount,
				"sales_target": self.sales_target_penalty_70,
				"min_leads": self.min_new_leads_per_month,
				"min_demos": self.min_demos_per_month
			}
		}
		
		return summary


@frappe.whitelist()
def get_default_roles_and_responsibilities():
	"""Return default roles and responsibilities text"""
	return """
	<ul>
		<li>Actively engage in sales activities to promote and sell products offered by Chundakadan Agencies, with a specific focus on promoting the seven designated brands: Sajin, Al Craft, Foins, Ausio, Deco, Ruby, and Carpt.</li>
		<li>Acquire a minimum of three (3) new leads per month to expand the customer base.</li>
		<li>Acquire and maintain comprehensive product knowledge to effectively communicate features and benefits to customers.</li>
		<li>Demonstrate professional behavior, including adherence to a formal dress code as specified by the Employer.</li>
		<li>Work with full potential to meet or exceed sales, lead generation, and cash collection targets.</li>
		<li>Maintain polite behavior with customers, ensuring courteous and respectful interactions at all times.</li>
		<li>Foster and maintain a highly professional and positive relationship with clients, customers, co-workers, and management to uphold the Company's reputation.</li>
		<li>Carry our product samples as always in order to promote the sales and increase market demand.</li>
	</ul>
	"""
