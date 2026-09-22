"""Number cards for the Approvals workspace.

Everything waiting on somebody, in one place: the approval chains
(leave, expense, advance, payment request, office expense voucher), the
Purchase Order workflow, cheques still to clear and the collection
chases that are due. Upserted on every migrate, like the dispatch cards.
"""

import json

import frappe

MODULE = "Chundakadan"
TODAY_JS = "frappe.datetime.get_today()"

# label, doctype, filters, dynamic filters, colour
CARDS = [
	("Leave Approvals Pending", "Leave Application",
	 [["Leave Application", "custom_approval_status", "=", "Pending"], ["Leave Application", "docstatus", "<", 2]], None, "#F59E0B"),
	("Expense Claims Pending", "Expense Claim",
	 [["Expense Claim", "custom_approval_status", "=", "Pending"], ["Expense Claim", "docstatus", "<", 2]], None, "#EF4444"),
	("Employee Advances Pending", "Employee Advance",
	 [["Employee Advance", "custom_approval_status", "=", "Pending"], ["Employee Advance", "docstatus", "<", 2]], None, "#8B5CF6"),
	("Payment Requests Pending", "Payment Request",
	 [["Payment Request", "custom_approval_status", "=", "Pending"], ["Payment Request", "docstatus", "<", 2]], None, "#0EA5E9"),
	("Office Expense Vouchers Pending", "Office Expense Voucher",
	 [["Office Expense Voucher", "custom_approval_status", "=", "Pending"], ["Office Expense Voucher", "docstatus", "<", 2]], None, "#F97316"),
	("Purchase Orders Awaiting Approval", "Purchase Order",
	 [["Purchase Order", "docstatus", "=", 0],
	  ["Purchase Order", "workflow_state", "in", [
		  "Pending Billing Verification", "Pending Sales Verification",
		  "Pending Accounts Verification", "Pending GM Approval"]]], None, "#3B82F6"),
	("Cheques To Collect", "Post Dated Cheque",
	 [["Post Dated Cheque", "status", "=", "Pending"], ["Post Dated Cheque", "docstatus", "=", 1]], None, "#22C55E"),
	("Follow-ups Due", "Customer Follow Up",
	 [["Customer Follow Up", "status", "=", "Open"]],
	 [["Customer Follow Up", "next_follow_up_date", "<=", TODAY_JS]], "#DC2626"),
]


def ensure_approval_number_cards(*args, **kwargs):
	for label, doctype, filters, dynamic, colour in CARDS:
		if not frappe.db.exists("DocType", doctype):
			continue
		values = {
			"label": label,
			"type": "Document Type",
			"document_type": doctype,
			"function": "Count",
			"filters_json": json.dumps(filters),
			"dynamic_filters_json": json.dumps(dynamic) if dynamic else None,
			"color": colour,
			"is_public": 1,
			"module": MODULE,
		}
		if frappe.db.exists("Number Card", label):
			doc = frappe.get_doc("Number Card", label)
			doc.update(values)
			doc.save(ignore_permissions=True)
		else:
			frappe.get_doc({"doctype": "Number Card", **values}).insert(ignore_permissions=True)
