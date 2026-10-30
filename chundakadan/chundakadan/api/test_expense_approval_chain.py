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
		holders = frappe.get_all(
			"Has Role", filters={"role": "HR Manager", "parenttype": "User"}, pluck="parent"
		)
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
		doc = frappe._dict(
			{
				"doctype": "Expense Claim",
				"current_approver": "someone@else.com",
				"current_approval_index": 0,
				"approval_flow": [],
			}
		)
		self.assertFalse(ea._caller_can_act_on(doc, hr))

	def test_accounts_and_gm_can_act_at_their_step(self):
		accounts = frappe.db.get_value("Has Role", {"role": ea.ROLE_ACCOUNTS, "parenttype": "User"}, "parent")
		gm = frappe.db.get_value("Has Role", {"role": ea.ROLE_GM, "parenttype": "User"}, "parent")
		if not (accounts and gm):
			self.skipTest("chain roles have no holders")
		doc = frappe._dict(
			{
				"doctype": "Expense Claim",
				"current_approver": accounts,
				"current_approval_index": 0,
				"approval_flow": [],
			}
		)
		self.assertTrue(ea._caller_can_act_on(doc, accounts))
		doc.current_approver = gm
		self.assertTrue(ea._caller_can_act_on(doc, gm))

	def test_claim_flow_is_two_steps_for_a_small_amount(self):
		employee = frappe.db.get_value("Employee", {"status": "Active", "company": COMPANY}, "name")
		expense_type = frappe.db.get_value("Expense Claim Type", {}, "name")
		if not (employee and expense_type):
			self.skipTest("no employee or expense claim type")
		claim = frappe.get_doc(
			{
				"doctype": "Expense Claim",
				"employee": employee,
				"company": COMPANY,
				"posting_date": frappe.utils.nowdate(),
				"approval_status": "Draft",
				"expenses": [
					{
						"expense_date": frappe.utils.nowdate(),
						"expense_type": expense_type,
						"amount": 100,
						"sanctioned_amount": 100,
					}
				],
			}
		)
		claim.insert(ignore_permissions=True)
		self.assertEqual([row.approver_role for row in claim.approval_flow], [ea.ROLE_ACCOUNTS, ea.ROLE_GM])
		self.assertEqual(claim.custom_approval_status, "Pending")


class TestWhyYouCannotAct(FrappeTestCase):
	"""The refusal has to say what is in the way.

	The GM read "You don't have permission to reject this Employee Advance"
	and took it for a rights problem; the advance was simply still with
	Accounts, one step earlier.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		self.accounts = frappe.db.get_value(
			"Has Role", {"role": ea.ROLE_ACCOUNTS, "parenttype": "User"}, "parent"
		)
		self.gm = frappe.db.get_value("Has Role", {"role": ea.ROLE_GM, "parenttype": "User"}, "parent")
		if not (self.accounts and self.gm):
			self.skipTest("chain roles have no holders")

	def tearDown(self):
		frappe.db.rollback()

	def _doc(self):
		return frappe._dict(
			{
				"doctype": "Employee Advance",
				"current_approver": self.accounts,
				"current_approval_index": 0,
				"approval_flow": [
					{"approver": self.accounts, "approver_role": ea.ROLE_ACCOUNTS},
					{"approver": self.gm, "approver_role": ea.ROLE_GM},
				],
			}
		)

	def test_it_names_who_the_document_is_with(self):
		message = ea._why_you_cannot_act(self._doc(), "Employee Advance", "reject", self.gm)
		self.assertIn(ea._who(self.accounts), message)

	def test_it_says_the_turn_is_coming(self):
		message = ea._why_you_cannot_act(self._doc(), "Employee Advance", "reject", self.gm)
		self.assertIn("comes to you", message)

	def test_it_never_calls_it_a_permission_problem(self):
		message = ea._why_you_cannot_act(self._doc(), "Employee Advance", "reject", self.gm)
		self.assertNotIn("permission", message.lower())

	def test_somebody_outside_the_chain_is_told_so(self):
		message = ea._why_you_cannot_act(
			self._doc(), "Employee Advance", "approve", "nobody@chundakadan.test"
		)
		self.assertIn("not on you", message)

	def test_with_no_chain_at_all_it_says_you_are_not_an_approver(self):
		doc = frappe._dict(
			{
				"doctype": "Expense Claim",
				"current_approver": None,
				"current_approval_index": 0,
				"approval_flow": [],
			}
		)
		message = ea._why_you_cannot_act(doc, "Expense Claim", "approve", self.gm)
		self.assertIn("not an approver", message)

	def test_who_falls_back_to_the_email(self):
		self.assertEqual(ea._who("nobody@chundakadan.test"), "nobody@chundakadan.test")


class TestOnePersonSignsOnce(FrappeTestCase):
	"""A manager standing in for a vacant post above them holds two of the
	chain's roles. Asking them to approve their own approval is no check at
	all, so the later step is dropped.

	The GM left on 2026-10-09 and the Deputy Sales & Marketing Manager took
	the GM's approvals, which put the same person at two steps of the
	Purchase Order and leave chains.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		self._real = ea._get_approver_by_role

	def tearDown(self):
		ea._get_approver_by_role = self._real
		frappe.db.rollback()

	def _flow_for(self, mapping, roles):
		ea._get_approver_by_role = lambda role: mapping.get(role)
		doc = frappe.new_doc("Employee Advance")
		ea._generate_approval_flow(doc, roles)
		return doc

	def test_the_same_person_appears_once(self):
		doc = self._flow_for(
			{ea.ROLE_ACCOUNTS: "one@test.com", ea.ROLE_GM: "one@test.com"},
			[ea.ROLE_ACCOUNTS, ea.ROLE_GM],
		)
		self.assertEqual([r.approver for r in doc.approval_flow], ["one@test.com"])

	def test_it_is_the_first_step_that_is_kept(self):
		"""So the document still travels as far up the chain as it would."""
		doc = self._flow_for(
			{ea.ROLE_ACCOUNTS: "one@test.com", ea.ROLE_GM: "one@test.com"},
			[ea.ROLE_ACCOUNTS, ea.ROLE_GM],
		)
		self.assertEqual(doc.approval_flow[0].approver_role, ea.ROLE_ACCOUNTS)

	def test_two_different_people_both_stay(self):
		doc = self._flow_for(
			{ea.ROLE_ACCOUNTS: "one@test.com", ea.ROLE_GM: "two@test.com"},
			[ea.ROLE_ACCOUNTS, ea.ROLE_GM],
		)
		self.assertEqual([r.approver for r in doc.approval_flow], ["one@test.com", "two@test.com"])

	def test_the_document_still_starts_with_somebody(self):
		doc = self._flow_for(
			{ea.ROLE_ACCOUNTS: "one@test.com", ea.ROLE_GM: "one@test.com"},
			[ea.ROLE_ACCOUNTS, ea.ROLE_GM],
		)
		self.assertEqual(doc.current_approver, "one@test.com")
		self.assertEqual(doc.current_approval_index, 0)
		self.assertEqual(doc.custom_approval_status, "Pending")

	def test_a_missing_role_holder_is_still_refused(self):
		ea._get_approver_by_role = lambda role: None
		doc = frappe.new_doc("Employee Advance")
		with self.assertRaises(frappe.ValidationError):
			ea._generate_approval_flow(doc, [ea.ROLE_ACCOUNTS])
