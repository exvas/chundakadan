import frappe


def execute():
	"""
	Update customer Overdue Invoice Restriction
	"""

	frappe.db.sql(""" UPDATE `tabCustomer` SET custom_overdue_invoice_restriction=1 """)
	frappe.db.commit()
