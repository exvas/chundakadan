import frappe

def validate_sales_invoice(doc, method):
	if doc.is_return or doc.get("custom_ignore_overdue_restriction"):
		return

	restriction_enabled = frappe.db.get_value("Customer", doc.customer, "custom_overdue_invoice_restriction")
	if not restriction_enabled:
		return

	overdue_invoices = check_overdue_unpaid_invoices(doc.customer, doc.posting_date)
	if overdue_invoices:
		invoice_list = "<ul>" + "".join([f"<li>{d.name} (Due: {d.due_date}, Outstanding: {d.outstanding_amount})</li>" for d in overdue_invoices]) + "</ul>"
		frappe.throw(
			f"Customer <b>{doc.customer}</b> has overdue unpaid invoices based on their payment schedule as of {doc.posting_date}:<br><br>{invoice_list}<br>"
			f"Please clear these outstanding payments before creating a new Sales Invoice.",
			title="Credit Restriction"
		)

@frappe.whitelist()
def check_overdue_unpaid_invoices(customer, posting_date=None):
	# Check if restriction is enabled for this customer
	restriction_enabled = frappe.db.get_value("Customer", customer, "custom_overdue_invoice_restriction")
	if not restriction_enabled:
		return []

	if not posting_date:
		posting_date = frappe.utils.today()

	# Find invoices where at least one payment schedule date has passed relative to the posting_date and there is still an outstanding amount
	overdue_invoices = frappe.db.sql("""
		SELECT DISTINCT si.name, ps.due_date, si.outstanding_amount
		FROM `tabSales Invoice` si
		JOIN `tabPayment Schedule` ps ON ps.parent = si.name
		WHERE si.docstatus = 1
		  AND si.customer = %s
		  AND si.outstanding_amount > 0
		  AND ps.due_date < %s
		ORDER BY ps.due_date ASC
	""", (customer, posting_date), as_dict=1)
	
	return overdue_invoices
