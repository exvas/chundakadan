import frappe

def execute():
	if not frappe.db.has_column("Customer", "custom_credit_days"):
		frappe.db.sql("ALTER TABLE `tabCustomer` ADD COLUMN `custom_credit_days` varchar(255)")
		
	frappe.db.sql("UPDATE `tabCustomer` SET custom_credit_days = 45")
