# Copyright (c) 2025, TBO Cloud and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class CleaningChecklist(Document):
	def validate(self):
		self.update_status()
	
	def on_submit(self):
		self.update_status()
	
	def on_cancel(self):
		self.status = "Cancelled"
	
	def update_status(self):
		if self.docstatus == 0:
			self.status = "Draft"
		elif self.docstatus == 1:
			# Check if all tasks are completed
			all_completed = True
			for item in self.cleaning_items:
				# Get current day
				import datetime
				day_abbr = datetime.datetime.strptime(str(self.date), '%Y-%m-%d').strftime('%a').lower()
				
				# Check if today's checkbox is checked
				if hasattr(item, day_abbr) and not getattr(item, day_abbr):
					all_completed = False
					break
			
			if all_completed:
				self.status = "Completed"
			else:
				self.status = "Pending"
		elif self.docstatus == 2:
			self.status = "Cancelled"
