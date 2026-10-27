"""Who carried the goods must stay on screen, on every tab that has a carrier.

The transporter is the first thing asked when a delivery is questioned days
later, and it was missing from both the Delivered and the Not Delivered tab —
the data was being fetched the whole time, only the column was absent, so
nothing failed and nobody could tell except by looking.
"""

import re

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.dispatch.api import LIST_FIELDS

DISPATCH_JS = frappe.get_app_path("chundakadan", "chundakadan", "page", "dispatch", "dispatch.js")
LABEL = re.compile(r'case "(\w+)":|(default):')


def column_blocks() -> dict[str, str]:
	"""The source of each tab's column list, keyed by tab."""
	source = open(DISPATCH_JS).read()
	body = source.split("\tcolumns() {", 1)[1].split("\n\tactions(", 1)[0]

	marks = list(LABEL.finditer(body))
	blocks = {}
	for i, mark in enumerate(marks):
		tab = mark.group(1) or "delivered"  # `default:` is the Delivered tab
		end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
		blocks[tab] = body[mark.end() : end]
	return blocks


class TestDispatchColumns(FrappeTestCase):
	def setUp(self):
		self.blocks = column_blocks()

	def test_every_tab_is_found(self):
		self.assertEqual(
			set(self.blocks),
			{"pending", "followup", "dispatched", "not_delivered", "delivered"},
			"the tabs moved — this test is reading the wrong part of the file",
		)

	def test_the_carrier_is_shown_wherever_there_is_one(self):
		for tab in ("followup", "dispatched", "not_delivered", "delivered"):
			with self.subTest(tab=tab):
				self.assertIn(
					"transporter",
					self.blocks[tab],
					f"the {tab} tab no longer names the transporter",
				)

	def test_pending_has_no_carrier_yet(self):
		self.assertNotIn(
			"transporter",
			self.blocks["pending"],
			"nothing is dispatched yet on this tab, so there is no carrier to name",
		)

	def test_the_api_actually_sends_it(self):
		for field in ("transporter", "transporter_name"):
			self.assertIn(field, LIST_FIELDS, "a column with nothing behind it renders blank")
