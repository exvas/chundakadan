# Copyright (c) 2025, TBO Cloud and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today, flt, formatdate


class PromotionLetter(Document):
	def validate(self):
		self.validate_employee()
		self.set_employee_id()
		self.fetch_current_details()
		self.calculate_salary_increment()
		self.set_default_content()
		self.update_status()
	
	def on_submit(self):
		self.status = "Issued"
		self.update_employee_details()
	
	def on_cancel(self):
		self.status = "Cancelled"
	
	def validate_employee(self):
		"""Validate employee exists and is active"""
		if self.employee:
			emp = frappe.get_doc("Employee", self.employee)
			if emp.status != "Active":
				frappe.msgprint(_("Warning: Employee {0} is not in Active status").format(self.employee), 
					indicator="orange")
	
	def set_employee_id(self):
		"""Auto-populate employee ID if not set"""
		if self.employee and not self.employee_id:
			employee_id = frappe.db.get_value("Employee", self.employee, "employee_number")
			if employee_id:
				self.employee_id = employee_id
	
	def fetch_current_details(self):
		"""Fetch current position, department, and grade from employee"""
		if self.employee and not self.current_position:
			emp = frappe.get_doc("Employee", self.employee)
			self.current_position = emp.designation
			self.current_department = emp.department
			self.current_grade = emp.grade if hasattr(emp, 'grade') else None
	
	def calculate_salary_increment(self):
		"""Calculate salary increment if new salary is provided"""
		if self.new_salary and self.employee:
			current_salary = frappe.db.get_value("Employee", self.employee, "ctc")
			if current_salary:
				self.salary_increment = flt(self.new_salary) - flt(current_salary)
	
	def set_default_content(self):
		"""Set default letter content and subject"""
		if not self.subject and self.new_position:
			self.subject = f"Promotion to {self.new_position}"
		
		if not self.letter_content and self.employee_name and self.new_position:
			self.letter_content = self.get_default_letter_content()
		
		if not self.employee_acceptance_text:
			self.employee_acceptance_text = f"I, {self.employee_name}, accept the promotion to the position of {self.new_position} as outlined above."
		
		if not self.reason_for_promotion:
			self.reason_for_promotion = self.get_default_reason()
		
		if not self.new_role_responsibilities:
			self.new_role_responsibilities = self.get_default_responsibilities()
	
	def get_default_letter_content(self):
		"""Generate default letter content matching the template"""
		effective_date_str = formatdate(self.effective_date) if self.effective_date else "the specified date"
		
		content = f"""<p><strong>To,</strong><br>
		{self.employee_name}<br>
		ID No: {self.employee_id or 'N/A'}<br>
		<strong>Subject:</strong> {self.subject}</p>
		
		<p>Dear {self.employee_name},</p>
		
		<p>We are pleased to inform you that, in recognition of your dedication, hard work, and 
		outstanding performance at {self.company or 'Chundakadan'} Agencies, you have been promoted to the position 
		of <strong>{self.new_position}</strong>. Effective from {effective_date_str}.</p>
		
		<p>Your consistent commitment to maintaining high standards in {self.new_department or 'your'} services, along 
		with your leadership skills and ability to work effectively with your team, has made you a 
		valuable asset to our organization. We are confident that you will excel in this new role and 
		continue to contribute to the success of {self.company or 'Chundakadan'} Agencies.</p>
		
		<p><strong>Details of Your New Role:</strong></p>
		<ul>
			<li><strong>Position:</strong> {self.new_position}</li>
			<li><strong>Department:</strong> {self.new_department or 'N/A'}</li>
			<li><strong>Reporting to:</strong> {frappe.db.get_value('Employee', self.reporting_to, 'employee_name') if self.reporting_to else 'N/A'}</li>
		</ul>
		
		<p>As a {self.new_position}, you will be responsible for {self.get_role_description()}. 
		We believe your skills and experience will greatly enhance the team's performance in this capacity.</p>
		
		<p>Once again, congratulations on your well-deserved promotion. We look forward to your 
		continued contributions to {self.company or 'Chundakadan'} Agencies.</p>
		
		<p>Sincerely,<br>
		<strong>General Manager</strong></p>
		"""
		
		return content
	
	def get_role_description(self):
		"""Get role description based on position"""
		role_descriptions = {
			"Housekeeping Supervisor": "overseeing the housekeeping team, ensuring the highest standards of cleanliness and efficiency, and coordinating with other departments to maintain a seamless operation",
			"Sales Manager": "leading the sales team, developing sales strategies, and achieving revenue targets",
			"Team Leader": "guiding and mentoring team members, ensuring quality deliverables, and coordinating with management",
			"Senior Executive": "handling complex tasks independently, mentoring junior staff, and contributing to strategic initiatives"
		}
		
		return role_descriptions.get(self.new_position, "performing duties as per your new role requirements")
	
	def get_default_reason(self):
		"""Get default reason for promotion"""
		return f"""<p>In recognition of your:</p>
		<ul>
			<li>Dedication and hard work</li>
			<li>Outstanding performance at {self.company or 'Chundakadan'} Agencies</li>
			<li>Consistent commitment to maintaining high standards</li>
			<li>Leadership skills and ability to work effectively with your team</li>
			<li>Valuable contributions to the organization</li>
		</ul>"""
	
	def get_default_responsibilities(self):
		"""Get default responsibilities for the new role"""
		return f"""<p>As {self.new_position}, your responsibilities will include:</p>
		<ul>
			<li>Leading and managing the team in {self.new_department or 'your department'}</li>
			<li>Ensuring high standards of work quality and efficiency</li>
			<li>Coordinating with other departments for seamless operations</li>
			<li>Reporting to {frappe.db.get_value('Employee', self.reporting_to, 'employee_name') if self.reporting_to else 'management'}</li>
			<li>Contributing to strategic planning and organizational goals</li>
		</ul>"""
	
	def update_status(self):
		"""Update status based on docstatus and acceptance"""
		if self.docstatus == 0:
			self.status = "Draft"
		elif self.docstatus == 2:
			self.status = "Cancelled"
		elif self.employee_signature and self.employee_signature_date:
			self.status = "Accepted"
	
	def update_employee_details(self):
		"""Update employee master with new designation and department"""
		# This will be done after employee accepts
		pass
	
	@frappe.whitelist()
	def accept_promotion(self):
		"""Employee accepts the promotion"""
		if self.docstatus == 1 and not self.employee_signature_date:
			self.employee_signature_date = today()
			self.status = "Accepted"
			self.save()
			
			# Update employee master
			if self.employee:
				emp = frappe.get_doc("Employee", self.employee)
				emp.designation = self.new_position
				emp.department = self.new_department
				if self.new_grade:
					emp.grade = self.new_grade
				if self.reporting_to:
					emp.reports_to = self.reporting_to
				emp.save()
				
				frappe.msgprint(_("Promotion accepted and employee details updated"), indicator="green")
		else:
			frappe.throw(_("Cannot accept promotion in current state"))
	
	@frappe.whitelist()
	def reject_promotion(self, reason=None):
		"""Employee rejects the promotion"""
		if self.docstatus == 1:
			self.status = "Rejected"
			if reason:
				self.remarks = f"Rejection Reason: {reason}\n\n{self.remarks or ''}"
			self.save()
			frappe.msgprint(_("Promotion has been rejected"), indicator="red")


@frappe.whitelist()
def get_employee_promotion_history(employee):
	"""Get promotion history for an employee"""
	if not employee:
		return []
	
	promotions = frappe.db.get_all("Promotion Letter",
		filters={"employee": employee, "docstatus": 1},
		fields=["name", "promotion_date", "effective_date", "current_position", "new_position", "status"],
		order_by="promotion_date desc"
	)
	
	return promotions
