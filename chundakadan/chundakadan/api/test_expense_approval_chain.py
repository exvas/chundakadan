import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.chundakadan.api import expense_approval as ea

COMPANY = "Chundakadan Agencies"


class TestExpenseApprovalChain(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_expense_claim_always_ends_with_the_gm(self):
		for amount in (1, 100, 4999, 5000, 50000):
			self.assertEqual(
				ea._build_chain(amount, "Expense Claim"),
				[ea.ROLE_ACCOUNTS, ea.ROLE_GM],
				amount,
			)

	def test_employee_advance_always_ends_with_the_gm(self):
		for amount in (1, 4999, 100000):
			self.assertEqual(
				ea._build_chain(amount, "Employee Advance"),
				[ea.ROLE_ACCOUNTS, ea.ROLE_GM],
				amount,
			)

	def test_payment_request_keeps_the_threshold(self):
		threshold = ea._get_threshold()
		self.assertEqual(ea._build_chain(threshold - 1, "Payment Request"), [ea.ROLE_ACCOUNTS])
		self.assertEqual(ea._build_chain(threshold + 1, "Payment Request"), [ea.ROLE_ACCOUNTS, ea.ROLE_GM])

	def test_hr_cannot_approve_outside_the_chain(self):
		self.assertNotIn("HR Manager", ea.ADMIN_ROLES)
		holders = frappe.get_all("Has Role", filters={"role": "HR Manager", "parenttype": "User"}, pluck="parent")
		hr = next(
			(
				u
				for u in holders
				if u != "Administrator"
				and not frappe.db.exists("Has Role", {"parent": u, "role": "System Manager"})
				and not frappe.db.exists("Has Role", {"parent": u, "role": ea.ROLE_GM})
				and not frappe.db.exists("Has Role", {"parent": u, "role": ea.ROLE_ACCOUNTS})
			),
			None,
		)
		if not hr:
			self.skipTest("every HR Manager also holds an admin or chain role")
		self.assertFalse(ea._user_has_admin_role(hr))
		doc = frappe._dict({"doctype": "Expense Claim", "current_approver": "someone@else.com", "current_approval_index": 0, "approval_flow": []})
		self.assertFalse(ea._caller_can_act_on(doc, hr))

	def test_accounts_and_gm_can_act_at_their_step(self):
		accounts = frappe.db.get_value("Has Role", {"role": ea.ROLE_ACCOUNTS, "parenttype": "User"}, "parent")
		gm = frappe.db.get_value("Has Role", {"role": ea.ROLE_GM, "parenttype": "User"}, "parent")
		if not (accounts and gm):
			self.skipTest("chain roles have no holders")
		doc = frappe._dict({"doctype": "Expense Claim", "current_approver": accounts, "current_approval_index": 0, "approval_flow": []})
		self.assertTrue(ea._caller_can_act_on(doc, accounts))
		doc.current_approver = gm
		self.assertTrue(ea._caller_can_act_on(doc, gm))

	def test_claim_flow_is_two_steps_for_a_small_amount(self):
		employee = frappe.db.get_value("Employee", {"status": "Active", "company": COMPANY}, "name")
		expense_type = frappe.db.get_value("Expense Claim Type", {}, "name")
		if not (employee and expense_type):
			self.skipTest("no employee or expense claim type")
		claim = frappe.get_doc({
			"doctype": "Expense Claim",
			"employee": employee,
			"company": COMPANY,
			"posting_date": frappe.utils.nowdate(),
			"approval_status": "Draft",
			"expenses": [{"expense_date": frappe.utils.nowdate(), "expense_type": expense_type, "amount": 100, "sanctioned_amount": 100}],
		})
		claim.insert(ignore_permissions=True)
		self.assertEqual([row.approver_role for row in claim.approval_flow], [ea.ROLE_ACCOUNTS, ea.ROLE_GM])
		self.assertEqual(claim.custom_approval_status, "Pending")
