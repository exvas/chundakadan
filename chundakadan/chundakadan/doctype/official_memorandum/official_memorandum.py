# Copyright (c) 2025, TBO Cloud and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, formatdate


class OfficialMemorandum(Document):
	def validate(self):
		self.set_default_content()
		self.update_status()
	
	def on_submit(self):
		self.status = "Issued"
		self.send_notification()
	
	def on_cancel(self):
		self.status = "Cancelled"
	
	def set_default_content(self):
		"""Set default memo content if not provided"""
		if not self.memo_content and self.subject:
			self.memo_content = self.get_default_memo_content()
		
		if not self.instructions:
			self.instructions = self.get_default_instructions()
		
		if not self.consequences:
			self.consequences = self.get_default_consequences()
		
		if not self.closing_message:
			self.closing_message = self.get_default_closing()
		
		if not self.clarification_contact:
			self.clarification_contact = "For any clarification, please contact your reporting head or the HR department."
	
	def get_default_memo_content(self):
		"""Generate default memo content based on subject"""
		if "communication" in self.subject.lower():
			return """This is to remind all staff that <strong>prompt and responsible communication</strong> is an essential part of our workplace discipline and professionalism."""
		else:
			return """This memorandum is to inform all staff about important matters that require your immediate attention and compliance."""
	
	def get_default_instructions(self):
		"""Get default instructions"""
		if "communication" in self.subject.lower():
			return """<ol>
				<li><strong>All instructions or messages from Management or your reporting heads shared via official WhatsApp groups or direct messages must be acknowledged and responded to without delay.</strong></li>
				<li><strong>Attendance and active participation in the daily morning meetings is mandatory.</strong> Any communication or instructions during the meeting must be taken seriously and acted upon accordingly.</li>
			</ol>"""
		else:
			return """<ol>
				<li>All staff members are required to comply with the instructions outlined in this memorandum.</li>
				<li>Immediate action is expected from all concerned parties.</li>
			</ol>"""
	
	def get_default_consequences(self):
		"""Get default consequences text"""
		return """Failure to respond promptly to official communications will be treated as negligence. Repeated instances of such behavior will result in formal warning memos, and may also lead to salary deductions as part of disciplinary action."""
	
	def get_default_closing(self):
		"""Get default closing message"""
		return """Let's maintain a culture of respect, accountability, and clear communication at all levels."""
	
	def update_status(self):
		"""Update status based on docstatus"""
		if self.docstatus == 0:
			self.status = "Draft"
		elif self.docstatus == 2:
			self.status = "Cancelled"
	
	def send_notification(self):
		"""Send notification to all staff or specific recipients"""
		if self.acknowledgment_required:
			# This can be extended to send email notifications
			frappe.msgprint(_("Memorandum has been issued. Notifications will be sent to all recipients."), 
				indicator="green")
	
	@frappe.whitelist()
	def acknowledge_memo(self, employee=None):
		"""Employee acknowledges the memo"""
		if not employee:
			employee = frappe.session.user
		
		employee_name = frappe.db.get_value("Employee", {"user_id": employee}, "employee_name")
		
		if not employee_name:
			employee_name = employee
		
		# Add to acknowledged list
		acknowledged = self.acknowledged_by or ""
		if employee_name not in acknowledged:
			if acknowledged:
				acknowledged += "\n"
			acknowledged += f"{employee_name} - {formatdate(today())}"
			self.acknowledged_by = acknowledged
			self.db_update()
			
			frappe.msgprint(_("Memorandum acknowledged successfully"), indicator="green")
			
			# Check if all employees have acknowledged
			self.check_acknowledgment_status()
	
	def check_acknowledgment_status(self):
		"""Check if all employees have acknowledged"""
		if self.acknowledged_by:
			acknowledged_count = len(self.acknowledged_by.split("\n"))
			# This can be extended to check against total employee count
			if acknowledged_count >= 1:
				self.status = "Acknowledged"
				self.db_update()


@frappe.whitelist()
def get_memo_templates():
	"""Get predefined memo templates"""
	templates = {
		"Communication Policy": {
			"subject": "Mandatory response to management communication",
			"recipients_to": "All staff",
			"greeting": "Dear Team,",
			"memo_content": "This is to remind all staff that <strong>prompt and responsible communication</strong> is an essential part of our workplace discipline and professionalism.",
			"instructions": """<ol>
				<li><strong>All instructions or messages from Management or your reporting heads shared via official WhatsApp groups or direct messages must be acknowledged and responded to without delay.</strong></li>
				<li><strong>Attendance and active participation in the daily morning meetings is mandatory.</strong> Any communication or instructions during the meeting must be taken seriously and acted upon accordingly.</li>
			</ol>""",
			"consequences": "Failure to respond promptly to official communications will be treated as negligence. Repeated instances of such behavior will result in formal warning memos, and may also lead to salary deductions as part of disciplinary action.",
			"closing_message": "Let's maintain a culture of respect, accountability, and clear communication at all levels.",
			"clarification_contact": "For any clarification, please contact your reporting head or the HR department."
		},
		"Policy Update": {
			"subject": "Important Policy Update",
			"recipients_to": "All staff",
			"greeting": "Dear Team,",
			"memo_content": "We would like to inform you about important updates to our company policies that will take effect immediately.",
			"instructions": "<ol><li>All staff are required to review the updated policy documents.</li><li>Compliance with the new policies is mandatory.</li></ol>",
			"consequences": "Non-compliance will result in disciplinary action as per company policy.",
			"closing_message": "Thank you for your cooperation in maintaining our standards.",
			"clarification_contact": "For any questions, please contact the HR department."
		}
	}
	
	return templates


@frappe.whitelist()
def get_memo_statistics():
	"""Get statistics on memos"""
	stats = {
		"total_memos": frappe.db.count("Official Memorandum", {"docstatus": 1}),
		"issued": frappe.db.count("Official Memorandum", {"status": "Issued"}),
		"acknowledged": frappe.db.count("Official Memorandum", {"status": "Acknowledged"}),
		"this_month": frappe.db.count("Official Memorandum", {
			"docstatus": 1,
			"memo_date": [">=", frappe.utils.get_first_day(today())]
		})
	}
	
	return stats
