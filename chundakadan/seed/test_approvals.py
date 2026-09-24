import json
import os

import frappe
from frappe.desk.doctype.number_card.number_card import get_result
from frappe.tests.utils import FrappeTestCase

from chundakadan.seed.approvals import CARDS, WORKSPACE, ensure_approval_number_cards, ensure_approvals_workspace


class TestApprovalsWorkspace(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		ensure_approval_number_cards()

	def tearDown(self):
		frappe.db.rollback()

	def _card(self, label):
		return frappe.get_doc("Number Card", label)

	def test_cards_exist_for_installed_doctypes(self):
		for label, doctype, *_ in CARDS:
			if not frappe.db.exists("DocType", doctype):
				continue
			card = self._card(label)
			self.assertEqual(card.document_type, doctype)
			self.assertEqual(card.function, "Count")

	def test_approval_cards_are_scoped_to_the_signed_in_user(self):
		for label, doctype, _filters, dynamic, _colour in CARDS:
			# These cards are not "waiting on me" by user: a cheque or a
			# follow-up belongs to nobody in particular, a PO is scoped by
			# workflow role, and an Item is scoped by the approval role.
			if doctype in ("Post Dated Cheque", "Customer Follow Up", "Purchase Order", "Item"):
				continue
			if not frappe.db.exists("DocType", doctype):
				continue
			card = self._card(label)
			self.assertTrue(card.dynamic_filters_json, label)
			self.assertIn("frappe.session.user", card.dynamic_filters_json, label)
			self.assertIn("current_approver", card.dynamic_filters_json, label)

	def test_purchase_order_card_follows_the_workflow_role(self):
		if not frappe.db.exists("DocType", "Purchase Order"):
			self.skipTest("no Purchase Order")
		card = self._card("Purchase Orders Awaiting Approval")
		for role, state in (
			("PO Approver", "Pending GM Approval"),
			("PO Accounts Manager", "Pending Accounts Verification"),
			("PO Deputy Sales Manager", "Pending Sales Verification"),
			("PO Billing Coordinator", "Pending Billing Verification"),
		):
			self.assertIn(role, card.dynamic_filters_json)
			self.assertIn(state, card.dynamic_filters_json)

	def test_counts_match_the_lists(self):
		for label, doctype, filters, dynamic, _colour in CARDS:
			if not frappe.db.exists("DocType", doctype) or dynamic:
				continue
			card = self._card(label)
			expected = len(frappe.get_all(doctype, filters=[f[1:] for f in filters], pluck="name"))
			self.assertEqual(get_result(card, card.filters_json), expected, label)

	def test_workspace_spec_is_first_in_the_sidebar(self):
		self.assertEqual(WORKSPACE["sequence_id"], 0.0)
		labels = {c[0] for c in CARDS}
		self.assertEqual(set(WORKSPACE["cards"]), labels)
		card_breaks = {l["label"] for l in WORKSPACE["links"] if l["type"] == "Card Break"}
		for block in WORKSPACE["content"]:
			if block["type"] == "number_card":
				self.assertIn(block["data"]["number_card_name"], labels)
			if block["type"] == "card":
				self.assertIn(block["data"]["card_name"], card_breaks)

	def test_lists_are_links_not_shortcuts(self):
		# a DocType shortcut always shows a global count badge, which
		# contradicts the per-user cards; links carry no count
		self.assertEqual(WORKSPACE["shortcuts"], [])
		self.assertTrue([l for l in WORKSPACE["links"] if l["type"] == "Link"])

	def test_workspace_is_created_once_and_never_overwritten(self):
		frappe.db.delete("Workspace", {"name": "Approvals"})
		self.assertEqual(ensure_approvals_workspace(), "created")
		ws = frappe.get_doc("Workspace", "Approvals")
		self.assertEqual((ws.sequence_id, ws.public, ws.icon), (0.0, 1, WORKSPACE["icon"]))
		self.assertEqual(len(ws.number_cards), len(CARDS))

		# whatever the site does to it afterwards must survive a migrate
		ws.icon = "star"
		ws.append("roles", {"role": "Accounts Manager"})
		ws.save()
		self.assertEqual(ensure_approvals_workspace(), "kept")
		ws.reload()
		self.assertEqual(ws.icon, "star")
		self.assertEqual([r.role for r in ws.roles], ["Accounts Manager"])

	def test_seed_is_idempotent(self):
		ensure_approval_number_cards()
		label = CARDS[0][0]
		self.assertEqual(frappe.db.count("Number Card", {"label": label}), 1)
