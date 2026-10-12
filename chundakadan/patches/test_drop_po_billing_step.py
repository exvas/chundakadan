import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.patches.drop_po_billing_step import execute
from chundakadan.seed.po_workflow import (
	BILLING,
	BILLING_ROLE,
	SALES,
	SALES_ROLE,
	WORKFLOW,
	ensure_po_workflow,
)


class TestTheBillingStepIsGone(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		ensure_po_workflow()
		if not frappe.db.exists("Workflow", WORKFLOW):
			self.skipTest("no Purchase Order workflow on this site")
		self._put_the_step_back()

	def tearDown(self):
		frappe.db.rollback()

	def _put_the_step_back(self):
		"""How the workflow looked before the step was dropped."""
		wf = frappe.get_doc("Workflow", WORKFLOW)
		for row in wf.transitions:
			if row.state == "Draft" and row.action == "Send for Verification":
				row.next_state = BILLING
			elif row.state == BILLING:
				row.allowed = BILLING_ROLE
		for row in wf.states:
			if row.state == BILLING:
				row.allow_edit = BILLING_ROLE
		wf.save(ignore_permissions=True)

	def _wf(self):
		return frappe.get_doc("Workflow", WORKFLOW)

	def test_sending_now_goes_straight_to_sales(self):
		execute()
		row = next(
			r for r in self._wf().transitions
			if r.state == "Draft" and r.action == "Send for Verification"
		)
		self.assertEqual(row.next_state, SALES)

	def test_an_order_parked_in_the_old_state_can_still_be_moved(self):
		"""Otherwise it is stranded a second time."""
		execute()
		for row in self._wf().transitions:
			if row.state == BILLING:
				self.assertEqual(row.allowed, SALES_ROLE)

	def test_the_old_state_is_still_a_legal_state(self):
		execute()
		self.assertIn(BILLING, [r.state for r in self._wf().states])

	def test_the_rest_of_the_chain_is_untouched(self):
		execute()
		moves = {
			(r.state, r.action): (r.next_state, r.allowed)
			for r in self._wf().transitions
		}
		self.assertEqual(moves[(SALES, "Verify")][0], "Pending Accounts Verification")
		self.assertEqual(moves[("Pending Accounts Verification", "Verify")][0], "Pending GM Approval")
		self.assertEqual(moves[("Pending GM Approval", "Approve")][0], "Approved")

	def test_a_stuck_order_is_moved_on(self):
		po = frappe.db.get_value("Purchase Order", {"docstatus": 0}, "name")
		if not po:
			self.skipTest("no draft purchase order on this site")
		before = frappe.db.get_value("Purchase Order", po, "workflow_state")
		frappe.db.set_value("Purchase Order", po, "workflow_state", BILLING, update_modified=False)
		execute()
		self.assertEqual(frappe.db.get_value("Purchase Order", po, "workflow_state"), SALES)
		frappe.db.set_value("Purchase Order", po, "workflow_state", before, update_modified=False)

	def test_running_it_twice_changes_nothing_more(self):
		execute()
		first = [(r.state, r.action, r.next_state, r.allowed) for r in self._wf().transitions]
		execute()
		self.assertEqual(
			first, [(r.state, r.action, r.next_state, r.allowed) for r in self._wf().transitions]
		)
