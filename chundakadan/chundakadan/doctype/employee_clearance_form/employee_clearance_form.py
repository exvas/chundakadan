# Copyright (c) 2026, Ashkar and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class EmployeeClearanceForm(Document):
	def autoname(self):
		from frappe.model.naming import make_autoname
		self.name = make_autoname('CDN/EC/.###./.YY.')
