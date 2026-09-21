"""Purchase Order approval chain.

Prepared by the purchaser, verified by billing coordinator → deputy sales
manager → accounts manager, approved by the GM. Approval submits the order.

Each step has its own role so the chain does not depend on a user's other
roles. Everything here is create-if-missing: an edit made in the UI (a new
member, a changed transition) survives the next migrate, like the role
profile seed. Use a patch for a deliberate change to the chain.
"""

import frappe

WORKFLOW = "Purchase Order Approval"
DOCTYPE = "Purchase Order"
STATE_FIELD = "workflow_state"

DRAFT = "Draft"
BILLING = "Pending Billing Verification"
SALES = "Pending Sales Verification"
ACCOUNTS = "Pending Accounts Verification"
GM = "Pending GM Approval"
APPROVED = "Approved"
REJECTED = "Rejected"

PURCHASER = "PO Purchaser"
BILLING_ROLE = "PO Billing Coordinator"
SALES_ROLE = "PO Deputy Sales Manager"
ACCOUNTS_ROLE = "PO Accounts Manager"
GM_ROLE = "PO Approver"

# role -> the user who holds it today. A user with a Role Profile has its
# roles reset from that profile on every save, so the workflow role has to go
# into the profile; each of these profiles has exactly this one user.
ROLE_PROFILES = {
	PURCHASER: "CDN Purchaser",
	BILLING_ROLE: "CDN Accountant",
	SALES_ROLE: "CDN Sales Admin",
	ACCOUNTS_ROLE: "CDN Accounts Manager",
	GM_ROLE: "CDN GM",
}

ROLE_USERS = {
	PURCHASER: "purchasechundakadan@gmail.com",  # Shahla A A, purchaser
	BILLING_ROLE: "acountschundakadan@gmail.com",  # Adarsh P, billing coordinator
	SALES_ROLE: "sales@chundakadan.in",  # Mohammed Razeel, deputy sales manager
	ACCOUNTS_ROLE: "accounts@chundakadan.in",  # Abdul Rashid, accounts manager
	GM_ROLE: "gm@chundakadan.in",  # Najeeb Sulaiman, general manager
}

# state, docstatus, role that may edit in this state, style
STATES = [
	(DRAFT, 0, PURCHASER, ""),
	(BILLING, 0, BILLING_ROLE, "Warning"),
	(SALES, 0, SALES_ROLE, "Warning"),
	(ACCOUNTS, 0, ACCOUNTS_ROLE, "Warning"),
	(GM, 0, GM_ROLE, "Warning"),
	(APPROVED, 1, GM_ROLE, "Success"),
	(REJECTED, 0, PURCHASER, "Danger"),
]

# state, action, next state, role
TRANSITIONS = [
	(DRAFT, "Send for Verification", BILLING, PURCHASER),
	(BILLING, "Verify", SALES, BILLING_ROLE),
	(BILLING, "Reject", REJECTED, BILLING_ROLE),
	(SALES, "Verify", ACCOUNTS, SALES_ROLE),
	(SALES, "Reject", REJECTED, SALES_ROLE),
	(ACCOUNTS, "Verify", GM, ACCOUNTS_ROLE),
	(ACCOUNTS, "Reject", REJECTED, ACCOUNTS_ROLE),
	(GM, "Approve", APPROVED, GM_ROLE),
	(GM, "Reject", REJECTED, GM_ROLE),
	(REJECTED, "Reopen", DRAFT, PURCHASER),
]


def ensure_po_workflow(*args, **kwargs):
	ensure_roles()
	ensure_permissions()
	ensure_state_masters()
	ensure_workflow()


def ensure_state_masters():
	"""Workflow rows link to Workflow State / Workflow Action Master records."""
	for state, _doc_status, _role, style in STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state, "style": style}).insert(ignore_permissions=True)
	for _state, action, _next_state, _role in TRANSITIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(ignore_permissions=True)


def ensure_roles():
	for role, user in ROLE_USERS.items():
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)
		profile = ROLE_PROFILES.get(role)
		if profile and frappe.db.exists("Role Profile", profile):
			doc = frappe.get_doc("Role Profile", profile)
			if role not in [r.role for r in doc.roles]:
				doc.append("roles", {"role": role})
				doc.save(ignore_permissions=True)
		if not frappe.db.exists("User", user):
			continue
		if not frappe.db.exists("Has Role", {"parent": user, "role": role}):
			user_doc = frappe.get_doc("User", user)
			user_doc.add_roles(role)
			if not frappe.db.exists("Has Role", {"parent": user, "role": role}):
				# the role profile owns this user's roles; saving re-reads it
				user_doc.save(ignore_permissions=True)


# saving a Purchase Order re-reads the item and supplier details
READ_DOCTYPES = ("Item", "Supplier")


def ensure_permissions():
	"""Every step needs write on the order; the GM also needs submit."""
	from frappe.permissions import add_permission, update_permission_property

	for role in ROLE_USERS:
		if not frappe.db.exists("Custom DocPerm", {"parent": DOCTYPE, "role": role, "permlevel": 0}):
			add_permission(DOCTYPE, role, 0)
		for ptype in ("read", "write", "print", "email"):
			update_permission_property(DOCTYPE, role, 0, ptype, 1, validate=False)
	for ptype in ("create", "submit"):
		update_permission_property(DOCTYPE, GM_ROLE, 0, ptype, 1, validate=False)
	update_permission_property(DOCTYPE, PURCHASER, 0, "create", 1, validate=False)
	for doctype in READ_DOCTYPES:
		for role in ROLE_USERS:
			if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
				add_permission(doctype, role, 0)
			update_permission_property(doctype, role, 0, "read", 1, validate=False)
		frappe.clear_cache(doctype=doctype)
	frappe.clear_cache(doctype=DOCTYPE)


def ensure_workflow():
	if frappe.db.exists("Workflow", WORKFLOW):
		existing = frappe.get_doc("Workflow", WORKFLOW)
		if not existing.send_email_alert:
			existing.db_set("send_email_alert", 1)
		return existing

	workflow = frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": WORKFLOW,
			"document_type": DOCTYPE,
			"workflow_state_field": STATE_FIELD,
			"is_active": 1,
			"send_email_alert": 1,  # mails the next approver, with the PO attached as PDF
			"states": [
				{
					"state": state,
					"doc_status": str(doc_status),
					"allow_edit": role,
					"style": style,
					"update_field": "status" if state == REJECTED else None,
					"update_value": "Closed" if state == REJECTED else None,
				}
				for state, doc_status, role, style in STATES
			],
			"transitions": [
				{"state": state, "action": action, "next_state": next_state, "allowed": role, "allow_self_approval": 1}
				for state, action, next_state, role in TRANSITIONS
			],
		}
	)
	workflow.insert(ignore_permissions=True)
	return workflow


def set_default_workflow_state(doc, method=None):
	"""Only the desk form fills the starting state; API/mobile inserts don't.

	Without it the order has no state and no transition is offered.
	"""
	if doc.docstatus == 0 and not doc.get(STATE_FIELD) and frappe.db.exists("Workflow", {"name": WORKFLOW, "is_active": 1}):
		doc.set(STATE_FIELD, DRAFT)
