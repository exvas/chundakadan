import frappe
from frappe.model.workflow import WorkflowTransitionError, apply_workflow, get_transitions
from frappe.tests.utils import FrappeTestCase

from chundakadan.seed.po_workflow import (
	ACCOUNTS,
	ACCOUNTS_ROLE,
	APPROVED,
	BILLING,
	BILLING_ROLE,
	DOCTYPE,
	DRAFT,
	GM,
	GM_ROLE,
	PURCHASER,
	REJECTED,
	ROLE_USERS,
	SALES,
	SALES_ROLE,
	STATES,
	TRANSITIONS,
	WORKFLOW,
	ensure_po_workflow,
)


class TestPOWorkflow(FrappeTestCase):
	def setUp(self):
		# each test rolls back, so seed per test rather than per class
		frappe.set_user("Administrator")
		ensure_po_workflow()
		# The workflow mails the next approver with the PO attached as a PDF.
		# This dev copy still has the old print format whose `addr` variable is
		# undefined when a PO has no shipping address, so rendering it throws.
		# Live renders fine; silence the mail here only.
		frappe.db.set_value("Workflow", WORKFLOW, "send_email_alert", 0)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_seed_enables_the_email_alert(self):
		frappe.db.set_value("Workflow", WORKFLOW, "send_email_alert", 0)
		ensure_po_workflow()
		self.assertEqual(frappe.db.get_value("Workflow", WORKFLOW, "send_email_alert"), 1)

	def test_workflow_states_and_transitions(self):
		wf = frappe.get_doc("Workflow", WORKFLOW)
		self.assertEqual((wf.document_type, wf.is_active, wf.workflow_state_field), (DOCTYPE, 1, "workflow_state"))
		self.assertEqual([(s.state, int(s.doc_status)) for s in wf.states], [(s[0], s[1]) for s in STATES])
		self.assertEqual([(t.state, t.action, t.next_state, t.allowed) for t in wf.transitions], TRANSITIONS)
		self.assertTrue(frappe.get_meta(DOCTYPE).get_field("workflow_state"))

	def test_roles_exist_and_are_assigned(self):
		for role, user in ROLE_USERS.items():
			self.assertTrue(frappe.db.exists("Role", role), role)
			if frappe.db.exists("User", user):
				self.assertTrue(frappe.db.exists("Has Role", {"parent": user, "role": role}), f"{user} {role}")

	def test_permissions(self):
		for role in ROLE_USERS:
			perm = frappe.db.get_value("Custom DocPerm", {"parent": DOCTYPE, "role": role, "permlevel": 0}, ["read", "write", "submit"], as_dict=True)
			self.assertTrue(perm, role)
			self.assertEqual((perm.read, perm.write), (1, 1), role)
		gm = frappe.db.get_value("Custom DocPerm", {"parent": DOCTYPE, "role": GM_ROLE, "permlevel": 0}, "submit")
		self.assertEqual(gm, 1)
		for doctype in ("Item", "Supplier"):
			for role in ROLE_USERS:
				self.assertEqual(frappe.db.get_value("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}, "read"), 1, f"{doctype} {role}")

	def test_seed_is_idempotent(self):
		before = frappe.db.count("Workflow Transition", {"parent": WORKFLOW})
		ensure_po_workflow()
		self.assertEqual(frappe.db.count("Workflow Transition", {"parent": WORKFLOW}), before)
		self.assertEqual(frappe.db.count("Workflow", {"document_type": DOCTYPE}), 1)

	def _draft_po(self):
		# the chain users are restricted to this company by User Permission
		company = "Chundakadan Agencies"
		supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
		item = frappe.db.get_value("Item", {"is_stock_item": 1, "disabled": 0, "has_variants": 0}, "name")
		warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name")
		po = frappe.get_doc({
			"doctype": DOCTYPE,
			"company": company,
			"supplier": supplier,
			"transaction_date": frappe.utils.nowdate(),
			"schedule_date": frappe.utils.nowdate(),
			"currency": frappe.get_cached_value("Company", company, "default_currency"),
			"conversion_rate": 1,
			"items": [{"item_code": item, "qty": 1, "rate": 100, "schedule_date": frappe.utils.nowdate(), "warehouse": warehouse}],
		})
		po.flags.ignore_permissions = True
		po.insert(ignore_permissions=True)
		self.assertEqual(po.workflow_state, DRAFT)  # set by the before_insert hook
		return po

	def _as(self, role):
		user = ROLE_USERS[role]
		if not frappe.db.exists("User", user):
			self.skipTest(f"{user} not on this site")
		frappe.set_user(user)

	def test_full_chain_approves_and_submits(self):
		po = self._draft_po()
		for role, action, expected in (
			(PURCHASER, "Send for Verification", BILLING),
			(BILLING_ROLE, "Verify", SALES),
			(SALES_ROLE, "Verify", ACCOUNTS),
			(ACCOUNTS_ROLE, "Verify", GM),
			(GM_ROLE, "Approve", APPROVED),
		):
			self._as(role)
			po = apply_workflow(frappe.get_doc(DOCTYPE, po.name), action)
			self.assertEqual(po.workflow_state, expected, f"{role} {action}")
		self.assertEqual(po.docstatus, 1)

	def test_wrong_role_cannot_move_the_chain(self):
		po = self._draft_po()
		self._as(BILLING_ROLE)  # billing cannot start the chain
		self.assertEqual([t.action for t in get_transitions(frappe.get_doc(DOCTYPE, po.name))], [])
		with self.assertRaises(WorkflowTransitionError):
			apply_workflow(frappe.get_doc(DOCTYPE, po.name), "Send for Verification")

	def test_verifier_can_reject_and_purchaser_reopens(self):
		po = self._draft_po()
		self._as(PURCHASER)
		apply_workflow(frappe.get_doc(DOCTYPE, po.name), "Send for Verification")
		self._as(BILLING_ROLE)
		po = apply_workflow(frappe.get_doc(DOCTYPE, po.name), "Verify")
		self.assertEqual(po.workflow_state, SALES)
		self._as(SALES_ROLE)
		po = apply_workflow(frappe.get_doc(DOCTYPE, po.name), "Reject")
		self.assertEqual((po.workflow_state, po.docstatus), (REJECTED, 0))
		self._as(PURCHASER)
		po = apply_workflow(frappe.get_doc(DOCTYPE, po.name), "Reopen")
		self.assertEqual(po.workflow_state, DRAFT)

	def test_gm_is_the_only_one_who_can_approve(self):
		po = self._draft_po()
		self._as(PURCHASER)
		apply_workflow(frappe.get_doc(DOCTYPE, po.name), "Send for Verification")
		for role in (BILLING_ROLE, SALES_ROLE, ACCOUNTS_ROLE):
			self._as(role)
			apply_workflow(frappe.get_doc(DOCTYPE, po.name), "Verify")
		self._as(ACCOUNTS_ROLE)
		with self.assertRaises(WorkflowTransitionError):
			apply_workflow(frappe.get_doc(DOCTYPE, po.name), "Approve")
		self.assertEqual(frappe.db.get_value(DOCTYPE, po.name, "docstatus"), 0)
