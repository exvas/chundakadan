# Copyright (c) 2025, TBO Cloud and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today, flt


class WarningLetter(Document):
	def validate(self):
		self.validate_employee()
		self.set_employee_id()
		self.calculate_penalty_amount()
		self.set_default_content()
		self.update_status()
	
	def on_submit(self):
		self.status = "Issued"
		self.create_salary_deduction()
		self.track_warning_history()
	
	def on_cancel(self):
		self.status = "Cancelled"
		self.cancel_salary_deduction()
	
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
	
	def calculate_penalty_amount(self):
		"""Calculate penalty amount based on salary deduction days"""
		if self.penalty_type == "Salary Deduction" and self.salary_deduction_days:
			# Get employee's daily salary
			if self.employee:
				salary = frappe.db.get_value("Employee", self.employee, "ctc")
				if salary:
					# Assuming 30 days in a month
					daily_salary = flt(salary) / 30
					self.penalty_amount = flt(self.salary_deduction_days) * daily_salary
	
	def set_default_content(self):
		"""Set default letter content based on violation type"""
		if not self.letter_content and self.violation_type:
			self.letter_content = self.get_default_letter_content()
		
		if not self.next_consequence:
			self.next_consequence = self.get_next_consequence_text()
	
	def get_default_letter_content(self):
		"""Generate default letter content based on violation type and warning type"""
		content = f"""<p>Dear {self.employee_name or 'Employee'},</p>"""
		
		if self.violation_type == "Negligence of Duty":
			content += """
			<p>This letter serves as a formal warning regarding your failure to adhere to the assigned route plan for 
			visiting retail and hardware shops on July 19, 2025. As identified by your reporting officer and Sales 
			Executive, it is mandatory to follow the pre-planned route map set by the company management. Your 
			unauthorized decision to deviate from this route plan without informing your reporting officer constitutes 
			negligence of duty.</p>
			
			<p>This breach of protocol has been noted, and as a consequence, you are hereby issued a {0}, 
			along with a deduction of {1} day's salary. Please be informed that any further instances of duty 
			negligence will result in serious disciplinary action, which may include termination of employment, 
			in accordance with company policy and applicable labor laws.</p>
			""".format(self.warning_type.lower() if self.warning_type else "warning", 
				self.salary_deduction_days or "one")
		else:
			content += f"""
			<p>This letter serves as a formal warning regarding your {self.violation_type.lower()} on {self.warning_date}.</p>
			
			<p>{self.violation_details or 'Details of the violation have been documented.'}</p>
			
			<p>This breach has been noted, and as a consequence, you are hereby issued a {self.warning_type.lower() if self.warning_type else 'warning'}."""
			
			if self.penalty_type == "Salary Deduction":
				content += f" A deduction of {self.salary_deduction_days or 'one'} day's salary will be applied."
			
			content += """</p>"""
		
		content += """
		<p>We expect you to strictly adhere to company policies and fulfill your responsibilities diligently 
		moving forward. Should you have any concerns or require clarification regarding your duties, you are 
		advised to discuss them with your reporting officer immediately.</p>
		
		<p>This warning is issued to ensure compliance with company policies and to maintain the expected 
		standards of performance. We trust you will take this matter seriously and take corrective measures to 
		avoid future violations.</p>
		
		<p>Sincerely,<br>
		{0}</p>
		""".format(self.company or "Your Company Name")
		
		return content
	
	def get_next_consequence_text(self):
		"""Get appropriate next consequence text based on warning type"""
		consequences = {
			"First Warning": "Any further violations will result in a Second Warning with increased penalties.",
			"Second Warning": "Any further violations will result in a Final Warning and may lead to suspension.",
			"Final Warning": "Any further violations will result in termination of employment.",
			"Show Cause Notice": "Failure to provide satisfactory explanation may result in immediate termination."
		}
		return consequences.get(self.warning_type, "Further violations will result in serious disciplinary action.")
	
	def update_status(self):
		"""Update status based on docstatus"""
		if self.docstatus == 0:
			self.status = "Draft"
		elif self.docstatus == 2:
			self.status = "Cancelled"
		elif self.employee_signature and self.employee_signature_date:
			self.status = "Acknowledged"
	
	def create_salary_deduction(self):
		"""Create salary deduction entry if applicable"""
		if self.penalty_type == "Salary Deduction" and self.salary_deduction_days and self.penalty_amount:
			# This can be integrated with payroll
			pass
	
	def cancel_salary_deduction(self):
		"""Cancel salary deduction if warning is cancelled"""
		if self.penalty_type == "Salary Deduction":
			# This can be integrated with payroll
			pass
	
	def track_warning_history(self):
		"""Track warning history for the employee"""
		# This can be used to count warnings and auto-escalate
		if self.employee:
			warning_count = frappe.db.count("Warning Letter", {
				"employee": self.employee,
				"docstatus": 1
			})
			
			if warning_count >= 3:
				frappe.msgprint(
					_("This employee has received {0} warnings. Consider further disciplinary action.").format(warning_count),
					indicator="red",
					alert=True
				)
	
	@frappe.whitelist()
	def acknowledge_warning(self):
		"""Employee acknowledges the warning"""
		if self.docstatus == 1:
			self.employee_signature_date = today()
			self.status = "Acknowledged"
			self.save()
			frappe.msgprint(_("Warning letter has been acknowledged"), indicator="green")


@frappe.whitelist()
def get_employee_warning_count(employee):
	"""Get the count of warnings for an employee"""
	if not employee:
		return 0
	
	return frappe.db.count("Warning Letter", {
		"employee": employee,
		"docstatus": 1
	})


@frappe.whitelist()
def get_employee_last_warning(employee):
	"""Get details of the last warning issued to an employee"""
	if not employee:
		return None
	
	last_warning = frappe.db.get_all("Warning Letter",
		filters={"employee": employee, "docstatus": 1},
		fields=["name", "warning_date", "warning_type", "violation_type", "subject"],
		order_by="warning_date desc",
		limit=1
	)
	
	return last_warning[0] if last_warning else None
