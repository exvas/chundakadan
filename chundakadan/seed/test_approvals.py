import json
import os

import frappe
from frappe.desk.doctype.number_card.number_card import get_result
from frappe.modules.import_file import import_file_by_path
from frappe.tests.utils import FrappeTestCase

from chundakadan.seed.approvals import CARDS, ensure_approval_number_cards

WORKSPACE_FILE = frappe.get_app_path("chundakadan", "chundakadan", "workspace", "approvals", "approvals.json")


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

	def test_counts_match_the_lists(self):
		for label, doctype, filters, dynamic, _colour in CARDS:
			if not frappe.db.exists("DocType", doctype) or dynamic:
				continue
			card = self._card(label)
			expected = len(frappe.get_all(doctype, filters=[f[1:] for f in filters], pluck="name"))
			self.assertEqual(get_result(card, card.filters_json), expected, label)

	def test_workspace_file_is_first_in_the_sidebar(self):
		with open(WORKSPACE_FILE) as f:
			ws = json.load(f)
		self.assertEqual(ws["sequence_id"], 0.0)
		self.assertEqual(ws["public"], 1)
		labels = {c[0] for c in CARDS}
		self.assertEqual({c["number_card_name"] for c in ws["number_cards"]}, labels)
		content = json.loads(ws["content"])
		shortcut_names = {s["label"] for s in ws["shortcuts"]}
		for block in content:
			if block["type"] == "number_card":
				self.assertIn(block["data"]["number_card_name"], labels)
			if block["type"] == "shortcut":
				self.assertIn(block["data"]["shortcut_name"], shortcut_names)

	def test_workspace_imports_and_lists_the_cards(self):
		import_file_by_path(WORKSPACE_FILE, force=True)
		ws = frappe.get_doc("Workspace", "Approvals")
		self.assertEqual(ws.sequence_id, 0.0)
		self.assertEqual(len(ws.number_cards), len(CARDS))
		self.assertTrue(ws.public)

	def test_seed_is_idempotent(self):
		ensure_approval_number_cards()
		label = CARDS[0][0]
		self.assertEqual(frappe.db.count("Number Card", {"label": label}), 1)
