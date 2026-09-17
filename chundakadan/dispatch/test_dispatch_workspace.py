import json
import os

import frappe
from frappe.desk.doctype.number_card.number_card import get_result
from frappe.modules.import_file import import_file_by_path
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, now_datetime, nowdate

from chundakadan.dispatch import constants as C
from chundakadan.dispatch.workspace import CARDS, ensure_dispatch_number_cards

WORKSPACE_FILE = frappe.get_app_path("chundakadan", "chundakadan", "workspace", "dispatch_center", "dispatch_center.json")


class TestDispatchWorkspace(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.invoices = frappe.get_all(
			"Sales Invoice", filters={"docstatus": 1, "is_return": 0}, pluck="name", limit=4, order_by="creation desc"
		)
		frappe.db.delete("Dispatch Log", {"sales_invoice": ["in", self.invoices]})

	def tearDown(self):
		frappe.db.rollback()

	def _log(self, invoice, **values):
		doc = frappe.get_doc({"doctype": "Dispatch Log", "sales_invoice": invoice, "grand_total": 100, **values})
		doc.flags.ignore_validate = True
		doc.flags.ignore_links = True
		doc.db_insert()

	def _card(self, label):
		return frappe.get_doc("Number Card", label)

	def _count(self, label):
		card = self._card(label)
		# the browser sends the card's own filters_json
		return get_result(card, card.filters_json)

	def test_cards_created_and_idempotent(self):
		ensure_dispatch_number_cards()
		ensure_dispatch_number_cards()
		for label, *_ in CARDS:
			card = self._card(label)
			self.assertEqual(card.document_type, "Dispatch Log")
			self.assertIn(["Dispatch Log", "invoice_cancelled", "=", 0], json.loads(card.filters_json))

	def test_card_counts_follow_status(self):
		ensure_dispatch_number_cards()
		before = {label: self._count(label) for label in ("Pending Dispatch", "In Transit", "Dispatched Today", "Not Delivered")}
		self._log(self.invoices[0], dispatch_status=C.PENDING, posting_date=nowdate())
		self._log(self.invoices[1], dispatch_status=C.DISPATCHED, dispatched_on=now_datetime())
		self._log(self.invoices[2], dispatch_status=C.NOT_DELIVERED)
		self._log(self.invoices[3], dispatch_status=C.PENDING, invoice_cancelled=1)
		after = {label: self._count(label) for label in before}
		self.assertEqual(after["Pending Dispatch"] - before["Pending Dispatch"], 1)  # cancelled one excluded
		self.assertEqual(after["In Transit"] - before["In Transit"], 1)
		self.assertEqual(after["Dispatched Today"] - before["Dispatched Today"], 1)
		self.assertEqual(after["Not Delivered"] - before["Not Delivered"], 1)

	def test_overdue_card_with_browser_dynamic_filter(self):
		ensure_dispatch_number_cards()
		card = self._card("Pending Over 2 Days")
		# dashboard_utils.js turns the JS expression into a date before calling get_result
		filters = json.loads(card.filters_json) + [["Dispatch Log", "posting_date", "<", add_days(nowdate(), -2)]]
		before = get_result(card, json.dumps(filters))
		self._log(self.invoices[0], dispatch_status=C.PENDING, posting_date=add_days(nowdate(), -5))
		self._log(self.invoices[1], dispatch_status=C.PENDING, posting_date=nowdate())
		self.assertEqual(get_result(card, json.dumps(filters)) - before, 1)

	def test_workspace_file(self):
		with open(WORKSPACE_FILE) as f:
			ws = json.load(f)
		labels = {c[0] for c in CARDS}
		self.assertEqual({c["number_card_name"] for c in ws["number_cards"]}, labels)
		content = json.loads(ws["content"])
		shortcut_names = {s["label"] for s in ws["shortcuts"]}
		for block in content:
			if block["type"] == "number_card":
				self.assertIn(block["data"]["number_card_name"], labels)
			if block["type"] == "shortcut":
				self.assertIn(block["data"]["shortcut_name"], shortcut_names)
		self.assertTrue(frappe.db.exists("Page", "dispatch"))
		# A workspace named "Dispatch" would take over the /app/dispatch page route.
		self.assertNotEqual(frappe.scrub(ws["name"]).replace("_", "-"), "dispatch")

	def test_workspace_imports(self):
		ensure_dispatch_number_cards()
		import_file_by_path(WORKSPACE_FILE, force=True)
		ws = frappe.get_doc("Workspace", "Dispatch Center")
		self.assertEqual(len(ws.number_cards), len(CARDS))
		self.assertEqual({r.role for r in ws.roles}, {C.ROLE, "System Manager", "Accounts Manager", "Sales Manager"})
