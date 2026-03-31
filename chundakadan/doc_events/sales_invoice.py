import frappe

def validate_sales_invoice(doc, method):
	check_customer_overdue_transactions(doc.customer)

@frappe.whitelist()
def check_customer_overdue_transactions(customer):
	if frappe.db.get_value("Customer", customer, "custom_overdue_invoice_restriction"):
		sales_invoice = frappe.db.sql(""" SELECT SUM(outstanding_amount) as total 
										FROM `tabSales Invoice` WHERE docstatus=1 and customer=%s""",customer,as_dict=1)

		if sales_invoice[0].total and sales_invoice[0].total > 0:
			frappe.throw("Customer " + customer + " has an outstanding invoice")
