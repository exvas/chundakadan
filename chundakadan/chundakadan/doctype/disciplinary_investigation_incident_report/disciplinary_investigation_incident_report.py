# Copyright (c) 2025, TBO Cloud and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, getdate


class DisciplinaryInvestigationIncidentReport(Document):
	def validate(self):
		self.validate_dates()
		self.validate_actions()
		self.update_status()
	
	def on_submit(self):
		self.status = "Investigating"
		self.create_warning_or_action()
	
	def on_cancel(self):
		self.status = "Cancelled"
	
	def validate_dates(self):
		"""Validate incident date is not in future"""
		if self.date_of_incident and getdate(self.date_of_incident) > getdate(today()):
			frappe.throw(_("Date of Incident cannot be in the future"))
		
		if self.report_date and self.date_of_incident:
			if getdate(self.report_date) < getdate(self.date_of_incident):
				frappe.throw(_("Report Date cannot be before Incident Date"))
	
	def validate_actions(self):
		"""Validate at least one action is selected"""
		if self.docstatus == 1:
			actions = [
				self.written_warning,
				self.did_not_pass_probation,
				self.medically_unfit,
				self.suspension,
				self.termination,
				self.contract_completion
			]
			
			if not any(actions):
				frappe.msgprint(_("No action to be taken has been selected"), indicator="orange")
	
	def update_status(self):
		"""Update status based on docstatus and actions"""
		if self.docstatus == 0:
			self.status = "Draft"
		elif self.docstatus == 2:
			self.status = "Cancelled"
		elif self.verified_by and self.verified_by_signature:
			self.status = "Completed"
		elif self.prepared_by and self.prepared_by_signature:
			self.status = "Investigating"
	
	def create_warning_or_action(self):
		"""Create warning letter or other actions based on selections"""
		if self.written_warning:
			# Get the first employee involved
			if self.employees_involved:
				employee = self.employees_involved[0].employee_name
				
				# Check if Warning Letter doctype exists
				if frappe.db.exists("DocType", "Warning Letter"):
					warning = frappe.new_doc("Warning Letter")
					warning.employee = employee
					warning.warning_date = today()
					warning.warning_type = "First Warning"
					warning.violation_type = "Other"
					warning.violation_details = self.description_of_incident
					warning.subject = f"Warning - Incident on {self.date_of_incident}"
					warning.penalty_type = "Warning Only"
					warning.flags.ignore_mandatory = True
					warning.save(ignore_permissions=True)
					
					frappe.msgprint(
						_("Warning Letter {0} has been created").format(warning.name),
						indicator="green",
						alert=True
					)
	
	@frappe.whitelist()
	def complete_investigation(self):
		"""Mark investigation as completed"""
		if self.docstatus == 1:
			self.status = "Action Taken"
			self.save()
			frappe.msgprint(_("Investigation marked as completed"), indicator="green")


@frappe.whitelist()
def get_employee_incident_history(employee):
	"""Get incident history for an employee"""
	if not employee:
		return []
	
	# Get incidents where employee is involved
	incidents = frappe.db.sql("""
		SELECT DISTINCT ie.parent, dir.date_of_incident, dir.place_of_incident, dir.status
		FROM `tabIncident Employee` ie
		INNER JOIN `tabDisciplinary Investigation Incident Report` dir 
			ON ie.parent = dir.name
		WHERE ie.employee_name = %s
		AND ie.parenttype = 'Disciplinary Investigation Incident Report'
		AND dir.docstatus = 1
		ORDER BY dir.date_of_incident DESC
	""", (employee,), as_dict=True)
	
	return incidents


@frappe.whitelist()
def get_incident_statistics():
	"""Get statistics on incidents"""
	stats = {
		"total_incidents": frappe.db.count("Disciplinary Investigation Incident Report", {"docstatus": 1}),
		"investigating": frappe.db.count("Disciplinary Investigation Incident Report", {"status": "Investigating"}),
		"completed": frappe.db.count("Disciplinary Investigation Incident Report", {"status": "Completed"}),
		"action_taken": frappe.db.count("Disciplinary Investigation Incident Report", {"status": "Action Taken"})
	}
	
	return stats
