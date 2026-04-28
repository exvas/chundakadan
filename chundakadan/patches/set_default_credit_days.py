import frappe

def execute():
	frappe.db.sql("UPDATE `tabCustomer` SET custom_credit_days = 45")
