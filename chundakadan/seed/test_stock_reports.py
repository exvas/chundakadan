import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.seed.stock_reports import (
	CARD_BREAK,
	REPORT,
	WORKSPACE,
	ensure_stock_count_link,
)


class TestStockCountOnTheStockWorkspace(FrappeTestCase):
	"""ERPNext's Stock Balance reads a reconciliation wrong and shows healthy
	stock as negative. The report that reads it right has to be the one people
	find."""

	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("Workspace", WORKSPACE) or not frappe.db.exists("Report", REPORT):
			self.skipTest("Stock workspace or report missing on this site")
		self._remove_it()

	def tearDown(self):
		frappe.db.rollback()

	def _remove_it(self):
		ws = frappe.get_doc("Workspace", WORKSPACE)
		if not any(r.link_to == REPORT for r in ws.links):
			return
		ws.set("links", [r for r in ws.links if r.link_to != REPORT])
		for row in ws.links:
			if row.type == "Card Break" and row.label == CARD_BREAK:
				row.link_count = max((row.link_count or 1) - 1, 0)
		ws.save(ignore_permissions=True)

	def _ws(self):
		return frappe.get_doc("Workspace", WORKSPACE)

	def test_the_link_is_added(self):
		ensure_stock_count_link()
		self.assertIn(REPORT, [r.link_to for r in self._ws().links])

	def test_it_lands_under_the_stock_reports_card(self):
		ensure_stock_count_link()
		rows = list(self._ws().links)
		section, found = None, None
		for row in rows:
			if row.type == "Card Break":
				section = row.label
			elif row.link_to == REPORT:
				found = section
		self.assertEqual(found, CARD_BREAK)

	def test_it_opens_as_a_query_report(self):
		ensure_stock_count_link()
		row = next(r for r in self._ws().links if r.link_to == REPORT)
		self.assertEqual(row.link_type, "Report")
		self.assertEqual(row.is_query_report, 1)

	def test_that_card_break_counts_its_own_links(self):
		ensure_stock_count_link()
		declared, actual, counting = None, 0, False
		for row in self._ws().links:
			if row.type == "Card Break":
				if counting:
					break
				if row.label == CARD_BREAK:
					declared, counting = row.link_count, True
			elif counting:
				actual += 1
		self.assertEqual(declared, actual)

	def test_the_other_links_survive(self):
		before = [r.link_to for r in self._ws().links if r.type == "Link"]
		ensure_stock_count_link()
		after = [r.link_to for r in self._ws().links if r.type == "Link"]
		for link in before:
			self.assertIn(link, after)
		self.assertEqual(len(after), len(before) + 1)

	def test_running_it_twice_adds_one_link(self):
		ensure_stock_count_link()
		ensure_stock_count_link()
		self.assertEqual(len([r for r in self._ws().links if r.link_to == REPORT]), 1)
