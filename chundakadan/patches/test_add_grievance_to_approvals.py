import json

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.patches.add_grievance_to_approvals import CARD, DOCTYPE, execute
from chundakadan.seed.approvals import ensure_approvals_workspace


class TestGrievanceOnTheApprovalsWorkspace(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		ensure_approvals_workspace()
		if not frappe.db.exists("Workspace", "Approvals"):
			self.skipTest("no Approvals workspace on this site")
		self._strip()

	def tearDown(self):
		frappe.db.rollback()

	def _strip(self):
		"""Put the workspace back to how a site that pre-dates the card looks."""
		ws = frappe.get_doc("Workspace", "Approvals")
		ws.set("number_cards", [r for r in ws.number_cards if r.number_card_name != CARD])
		ws.set("links", [r for r in ws.links if r.link_to != DOCTYPE])
		for row in ws.links:
			if row.type == "Card Break" and row.label == "Approvals":
				row.link_count = max((row.link_count or 1) - 1, 0)
		content = [
			b for b in json.loads(ws.content or "[]")
			if b.get("data", {}).get("number_card_name") != CARD
		]
		ws.content = json.dumps(content)
		ws.save(ignore_permissions=True)

	def _ws(self):
		return frappe.get_doc("Workspace", "Approvals")

	def test_the_card_is_added(self):
		execute()
		ws = self._ws()
		self.assertIn(CARD, [r.number_card_name for r in ws.number_cards])

	def test_the_card_is_on_the_dashboard(self):
		execute()
		content = json.loads(self._ws().content)
		self.assertTrue(any(
			b.get("data", {}).get("number_card_name") == CARD for b in content
		))

	def test_the_card_sits_with_the_other_cards(self):
		"""Not after the link sections, where nobody would see it."""
		execute()
		content = json.loads(self._ws().content)
		types = [b["type"] for b in content]
		index = next(
			i for i, b in enumerate(content)
			if b.get("data", {}).get("number_card_name") == CARD
		)
		after = types[index + 1:]
		self.assertNotIn("number_card", after, "a card ended up after the lists")

	def test_the_list_link_is_added(self):
		execute()
		self.assertIn(DOCTYPE, [r.link_to for r in self._ws().links])

	def test_the_card_break_counts_the_new_link(self):
		"""Only the break the patch touches.

		Another section can legitimately be short: a link whose target is
		not installed on a site is dropped when the workspace is seeded,
		and its declared count still counts it.
		"""
		execute()
		declared, actual = None, 0
		counting = False
		for row in self._ws().links:
			if row.type == "Card Break":
				if counting:
					break
				if row.label == "Approvals":
					declared, counting = row.link_count, True
			elif counting:
				actual += 1
		self.assertEqual(declared, actual)

	def test_the_other_links_survive(self):
		"""The patch rebuilds the link table to place the new row."""
		before = [r.link_to for r in self._ws().links if r.type == "Link"]
		execute()
		after = [r.link_to for r in self._ws().links if r.type == "Link"]
		for link in before:
			self.assertIn(link, after)
		self.assertEqual(len(after), len(before) + 1)

	def test_running_it_twice_changes_nothing_more(self):
		execute()
		before = self._ws()
		execute()
		after = self._ws()
		self.assertEqual(
			len([r for r in after.number_cards if r.number_card_name == CARD]), 1
		)
		self.assertEqual(len([r for r in after.links if r.link_to == DOCTYPE]), 1)
		self.assertEqual(len(after.links), len(before.links))
