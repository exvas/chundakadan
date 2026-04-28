import frappe

def validate_sales_invoice(doc, method):
	pass

@frappe.whitelist()
def check_overdue_unpaid_invoices(customer):
	# Get custom_credit_days from Customer
	credit_days = frappe.db.get_value("Customer", customer, "custom_credit_days")
	if credit_days is None:
		credit_days = 45 # Default as per user requirement
	
	# Find invoices created more than 'credit_days' ago that are still unpaid
	overdue_invoices = frappe.db.sql("""
		SELECT name, creation, outstanding_amount
		FROM `tabSales Invoice`
		WHERE docstatus = 1
		  AND customer = %s
		  AND outstanding_amount > 0
		  AND DATEDIFF(CURDATE(), creation) > %s
	""", (customer, credit_days), as_dict=1)
	
	return overdue_invoices
