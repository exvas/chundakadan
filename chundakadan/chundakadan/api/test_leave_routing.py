"""Which roles must sign a leave application, and in what order.

These run without a database: role_sequence_for is pure, which is the point
of having split it out. The routing is what goes wrong, and it went wrong
unnoticed until a live application showed the wrong chain.
"""

import unittest

from chundakadan.chundakadan.api.leave import role_sequence_for

SALES = ["Sales HOD Leave Approver", "HR Leave Approver", "GM Leave Approver"]
ACCOUNTS = ["Accounts Manager Leave Approver", "HR Leave Approver", "GM Leave Approver"]
HR_GM = ["HR Leave Approver", "GM Leave Approver"]
SALES_DEPT = "Sales& Marketing - CA"


class TestSalesChain(unittest.TestCase):
	def test_the_designations_from_the_client_table(self):
		for designation in (
			"Business Development Executive", "Senior Business Development Executive",
			"Business Development Co-ordinator", "Brand Co-ordinator", "Area Sales Manager",
			"Sales Officer", "Marketing Specialist", "Dispatch Coordinator", "Sales Executive",
		):
			self.assertEqual(role_sequence_for(designation, SALES_DEPT), SALES, designation)

	def test_customer_relations_executive_reaches_the_sales_hod(self):
		"""The live case: Fathima Rasla K was going straight to HR."""
		self.assertEqual(role_sequence_for("Customer Relations Executive", SALES_DEPT), SALES)

	def test_it_works_even_without_a_department(self):
		self.assertEqual(role_sequence_for("Customer Relations Executive", None), SALES)

	def test_a_designation_nobody_listed_still_follows_the_department(self):
		"""The safety net: anyone under Marketing goes to the SM/DM first."""
		for designation in ("Brand Ambassador", "Telecaller", None, ""):
			self.assertEqual(role_sequence_for(designation, SALES_DEPT), SALES, designation)
		self.assertEqual(role_sequence_for("Anything", "Marketing - CHS"), SALES)


class TestNobodyApprovesTheirOwnLeave(unittest.TestCase):
	def test_the_sales_hods_skip_their_own_chain(self):
		for designation in ("Sales & Marketing Manager", "Deputy Sales & Marketing Manager"):
			self.assertEqual(role_sequence_for(designation, SALES_DEPT), HR_GM, designation)

	def test_the_accounts_manager_skips_their_own_chain(self):
		self.assertEqual(
			role_sequence_for("Accounts Manager", "Finance & Procurement - CA"), HR_GM
		)

	def test_the_gm_is_signed_off_by_hr_alone(self):
		self.assertEqual(
			role_sequence_for("General Manager", "General Manager - CA"), ["HR Leave Approver"]
		)

	def test_hr_staff_go_straight_to_the_gm(self):
		for designation in ("HR Associate", "Administration Co-ordinator", "HR Assistant"):
			self.assertEqual(
				role_sequence_for(designation, "HR - CA"), ["GM Leave Approver"], designation
			)


class TestAccountsChain(unittest.TestCase):
	def test_the_designations_from_the_client_table(self):
		for designation in ("Accountant", "Purchaser", "Purchase Coordinator", "Billing Staff"):
			self.assertEqual(
				role_sequence_for(designation, "Finance & Procurement - CA"), ACCOUNTS, designation
			)

	def test_an_unlisted_finance_title_follows_the_department(self):
		for department in ("Finance & Procurement - CA", "Accounts - CA", "Purchase - CA"):
			self.assertEqual(role_sequence_for("Ledger Clerk", department), ACCOUNTS, department)


class TestEverybodyElse(unittest.TestCase):
	def test_floor_dispatch_and_retail_keep_the_plain_chain(self):
		"""The client's sheet puts these rows on HR -> GM; the department
		safety net must not quietly promote them."""
		for department, designation in (
			("Dispatch - CA", "Floor Assistant"),
			("Dispatch - CA", "House-keeping Assistant"),
			("Dispatch - CA", "Floor Manager"),
			("Floor Management - CA", "Floor Assistant"),
			("Retail Operations Department - CA", "Showroom Manager"),
		):
			self.assertEqual(role_sequence_for(designation, department), HR_GM, designation)

	def test_a_dispatch_co_ordinator_is_sales_by_title(self):
		"""Afeefa sits in Sales& Marketing and the title is on the sales list."""
		self.assertEqual(role_sequence_for("Dispatch Coordinator", "Sales& Marketing - CA"), SALES)


class TestTheChainIsAlwaysUsable(unittest.TestCase):
	def test_every_chain_ends_at_someone_and_has_no_repeats(self):
		cases = [
			("Customer Relations Executive", SALES_DEPT),
			("Accountant", "Finance & Procurement - CA"),
			("General Manager", "General Manager - CA"),
			("HR Associate", "HR - CA"),
			("Floor Assistant", "Dispatch - CA"),
			("Unknown Title", "Sales& Marketing - CA"),
			(None, None),
		]
		for designation, department in cases:
			chain = role_sequence_for(designation, department)
			self.assertTrue(chain, f"{designation} got an empty chain")
			self.assertEqual(len(chain), len(set(chain)), f"{designation} repeats an approver")
			for role in chain:
				self.assertTrue(role.endswith("Leave Approver"), role)


if __name__ == "__main__":
	unittest.main()
