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

# Cards say "waiting on you", so they are scoped to the signed-in user:
# the approval chains match `current_approver`, and the Purchase Order
# workflow matches the states the user's role can act on. Dynamic filters
# are JS, evaluated in the browser.
MINE = "frappe.session.user"
PO_STATES_FOR_MY_ROLE = (
	"(frappe.user_roles.includes('PO Approver') ? ['Pending GM Approval'] : "
	"frappe.user_roles.includes('PO Accounts Manager') ? ['Pending Accounts Verification'] : "
	"frappe.user_roles.includes('PO Deputy Sales Manager') ? ['Pending Sales Verification'] : "
	"frappe.user_roles.includes('PO Billing Coordinator') ? ['Pending Billing Verification'] : "
	"['__none__'])"
)

# label, doctype, filters, dynamic filters, colour
CARDS = [
	("Leave Approvals Pending", "Leave Application",
	 [["Leave Application", "custom_approval_status", "=", "Pending"], ["Leave Application", "docstatus", "<", 2]],
	 [["Leave Application", "current_approver", "=", MINE]], "#F59E0B"),
	("Expense Claims Pending", "Expense Claim",
	 [["Expense Claim", "custom_approval_status", "=", "Pending"], ["Expense Claim", "docstatus", "<", 2]],
	 [["Expense Claim", "current_approver", "=", MINE]], "#EF4444"),
	("Employee Advances Pending", "Employee Advance",
	 [["Employee Advance", "custom_approval_status", "=", "Pending"], ["Employee Advance", "docstatus", "<", 2]],
	 [["Employee Advance", "current_approver", "=", MINE]], "#8B5CF6"),
	("Payment Requests Pending", "Payment Request",
	 [["Payment Request", "custom_approval_status", "=", "Pending"], ["Payment Request", "docstatus", "<", 2]],
	 [["Payment Request", "current_approver", "=", MINE]], "#0EA5E9"),
	("Office Expense Vouchers Pending", "Office Expense Voucher",
	 [["Office Expense Voucher", "custom_approval_status", "=", "Pending"], ["Office Expense Voucher", "docstatus", "<", 2]],
	 [["Office Expense Voucher", "current_approver", "=", MINE]], "#F97316"),
	("Purchase Orders Awaiting Approval", "Purchase Order",
	 [["Purchase Order", "docstatus", "=", 0]],
	 [["Purchase Order", "workflow_state", "in", PO_STATES_FOR_MY_ROLE]], "#3B82F6"),
	("Cheques To Collect", "Post Dated Cheque",
	 [["Post Dated Cheque", "status", "=", "Pending"], ["Post Dated Cheque", "docstatus", "=", 1]], None, "#22C55E"),
	("Work Summaries Pending", "Daily Work Summary",
	 [["Daily Work Summary", "custom_approval_status", "in", ["Pending", "Partially Approved"]],
	  ["Daily Work Summary", "docstatus", "=", 0]],
	 [["Daily Work Summary", "current_approver", "=", MINE]], "#6366F1"),
	("Items Awaiting Approval", "Item",
	 [["Item", "custom_approval_status", "=", "Pending"]], None, "#14B8A6"),
	("Follow-ups Due", "Customer Follow Up",
	 [["Customer Follow Up", "status", "=", "Open"]],
	 [["Customer Follow Up", "next_follow_up_date", "<=", TODAY_JS]], "#DC2626"),
]


WORKSPACE = {
 "name": "Approvals",
 "title": "Approvals",
 "label": "Approvals",
 "module": "Chundakadan",
 "icon": "check",
 "indicator_color": "orange",
 "sequence_id": 0.0,
 "content": [
  {
   "id": "ap_hdr",
   "type": "header",
   "data": {
    "text": "<span class=\"h4\"><b>Waiting on you</b></span>",
    "col": 12
   }
  },
  {
   "id": "ap_nc0",
   "type": "number_card",
   "data": {
    "number_card_name": "Leave Approvals Pending",
    "col": 3
   }
  },
  {
   "id": "ap_nc1",
   "type": "number_card",
   "data": {
    "number_card_name": "Expense Claims Pending",
    "col": 3
   }
  },
  {
   "id": "ap_nc2",
   "type": "number_card",
   "data": {
    "number_card_name": "Employee Advances Pending",
    "col": 3
   }
  },
  {
   "id": "ap_nc3",
   "type": "number_card",
   "data": {
    "number_card_name": "Payment Requests Pending",
    "col": 3
   }
  },
  {
   "id": "ap_nc4",
   "type": "number_card",
   "data": {
    "number_card_name": "Office Expense Vouchers Pending",
    "col": 3
   }
  },
  {
   "id": "ap_nc5",
   "type": "number_card",
   "data": {
    "number_card_name": "Purchase Orders Awaiting Approval",
    "col": 3
   }
  },
  {
   "id": "ap_nc6",
   "type": "number_card",
   "data": {
    "number_card_name": "Cheques To Collect",
    "col": 3
   }
  },
  {
   "id": "ap_nc7",
   "type": "number_card",
   "data": {
    "number_card_name": "Follow-ups Due",
    "col": 3
   }
  },
  {
   "id": "ap_nc8",
   "type": "number_card",
   "data": {
    "number_card_name": "Work Summaries Pending",
    "col": 3
   }
  },
  {
   "id": "ap_nc9",
   "type": "number_card",
   "data": {
    "number_card_name": "Items Awaiting Approval",
    "col": 3
   }
  },
  {
   "id": "ap_hdr2",
   "type": "header",
   "data": {
    "text": "<span class=\"h5\">Open the lists</span>",
    "col": 12
   }
  },
  {
   "id": "ap_card1",
   "type": "card",
   "data": {
    "card_name": "Approvals",
    "col": 4
   }
  },
  {
   "id": "ap_card2",
   "type": "card",
   "data": {
    "card_name": "Collection",
    "col": 4
   }
  }
 ],
 "cards": [
  "Leave Approvals Pending",
  "Expense Claims Pending",
  "Employee Advances Pending",
  "Payment Requests Pending",
  "Office Expense Vouchers Pending",
  "Purchase Orders Awaiting Approval",
  "Cheques To Collect",
  "Follow-ups Due",
  "Work Summaries Pending",
  "Items Awaiting Approval"
 ],
 "shortcuts": [],
 "links": [
  {
   "type": "Card Break",
   "label": "Approvals",
   "hidden": 0,
   "is_query_report": 0,
   "link_count": 5,
   "onboard": 0
  },
  {
   "type": "Link",
   "link_type": "DocType",
   "link_to": "Leave Application",
   "label": "Leave Application",
   "hidden": 0,
   "is_query_report": 0,
   "link_count": 0,
   "onboard": 0
  },
  {
   "type": "Link",
   "link_type": "DocType",
   "link_to": "Expense Claim",
   "label": "Expense Claim",
   "hidden": 0,
   "is_query_report": 0,
   "link_count": 0,
   "onboard": 0
  },
  {
   "type": "Link",
   "link_type": "DocType",
   "link_to": "Employee Advance",
   "label": "Employee Advance",
   "hidden": 0,
   "is_query_report": 0,
   "link_count": 0,
   "onboard": 0
  },
  {
   "type": "Link",
   "link_type": "DocType",
   "link_to": "Daily Work Summary",
   "label": "Daily Work Summary",
   "hidden": 0,
   "is_query_report": 0,
   "link_count": 0,
   "onboard": 0
  },
  {
   "type": "Link",
   "link_type": "DocType",
   "link_to": "Purchase Order",
   "label": "Purchase Order",
   "hidden": 0,
   "is_query_report": 0,
   "link_count": 0,
   "onboard": 0
  },
  {
   "type": "Card Break",
   "label": "Collection",
   "hidden": 0,
   "is_query_report": 0,
   "link_count": 3,
   "onboard": 0
  },
  {
   "type": "Link",
   "link_type": "DocType",
   "link_to": "Post Dated Cheque",
   "label": "Post Dated Cheque",
   "hidden": 0,
   "is_query_report": 0,
   "link_count": 0,
   "onboard": 0
  },
  {
   "type": "Link",
   "link_type": "DocType",
   "link_to": "Customer Follow Up",
   "label": "Customer Follow Up",
   "hidden": 0,
   "is_query_report": 0,
   "link_count": 0,
   "onboard": 0
  },
  {
   "type": "Link",
   "link_type": "Report",
   "link_to": "Post Dated Cheque Report",
   "label": "Post Dated Cheque Report",
   "hidden": 0,
   "is_query_report": 1,
   "link_count": 0,
   "onboard": 0,
   "report_ref_doctype": "Post Dated Cheque"
  }
 ],
 "roles": []
}


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


def ensure_approvals_workspace(*args, **kwargs):
	"""Cards first, then the workspace — created only if it is missing, so
	role or icon changes made in the UI survive the next app update."""
	from chundakadan.seed.workspaces import ensure_workspace

	ensure_approval_number_cards()
	return ensure_workspace(WORKSPACE)
