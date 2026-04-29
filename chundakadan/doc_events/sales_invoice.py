import frappe

def validate_sales_invoice(doc, method):
	if doc.is_return:
		return

	restriction_enabled = frappe.db.get_value("Customer", doc.customer, "custom_overdue_invoice_restriction")
	if not restriction_enabled:
		return

	overdue_invoices = check_overdue_unpaid_invoices(doc.customer)
	if overdue_invoices:
		invoice_list = "<ul>" + "".join([f"<li>{d.name} (Outstanding: {d.outstanding_amount})</li>" for d in overdue_invoices]) + "</ul>"
		frappe.throw(
			f"Customer <b>{doc.customer}</b> has overdue unpaid invoices beyond the permitted credit days:<br><br>{invoice_list}<br>"
			f"Please clear these outstanding payments before creating a new Sales Invoice.",
			title="Credit Days Restriction"
		)

@frappe.whitelist()
def check_overdue_unpaid_invoices(customer):
	# Check if restriction is enabled for this customer
	restriction_enabled = frappe.db.get_value("Customer", customer, "custom_overdue_invoice_restriction")
	if not restriction_enabled:
		return []

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
