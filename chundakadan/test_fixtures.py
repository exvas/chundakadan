"""Our fixtures must not carry another app's fields.

Saving Customize Form on the live site stamps every custom field on that
doctype with our module, so the next export quietly adopts india_compliance's
fields as ours. One of them — Company.bank_details_for_printing, a Table
pointing at india_compliance's `Company Print Options` — took the whole test
suite down on a bench without india_compliance: Frappe walks Company's link
fields while building its test records and throws DoesNotExistError on a child
doctype we do not ship. Nothing failed; nothing ran.
"""

import json
import os

import frappe
from frappe.tests.utils import FrappeTestCase

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "custom_field.json")

# the apps a chundakadan bench is guaranteed to have
OUR_APPS = {"frappe", "erpnext", "hrms", "chundakadan"}

LINKING = ("Link", "Table", "Table MultiSelect")


def app_owning(doctype: str) -> str | None:
	module = frappe.db.get_value("DocType", doctype, "module")
	if not module:
		return None
	return frappe.db.get_value("Module Def", module, "app_name")


class TestCustomFieldFixture(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		with open(FIXTURE) as f:
			cls.fields = json.load(f)

	def test_the_fixture_is_not_empty(self):
		"""Guards the two tests below from passing on an empty list."""
		self.assertGreater(len(self.fields), 100)

	def test_no_field_points_at_a_doctype_we_do_not_ship(self):
		strangers = []
		for cf in self.fields:
			options = (cf.get("options") or "").strip()
			if cf.get("fieldtype") not in LINKING or not options:
				continue
			owner = app_owning(options)
			if owner is None or owner not in OUR_APPS:
				strangers.append(f"{cf.get('dt')}.{cf.get('fieldname')} -> {options} ({owner or 'missing'})")

		self.assertEqual(
			strangers,
			[],
			"these fixture fields link to a DocType this bench may not have, "
			"which kills the test bootstrap on a site without that app: " + "; ".join(strangers),
		)

	def test_no_field_fetches_a_column_another_app_owns(self):
		"""`fetch_from` is a SELECT at save time. Ours used to read
		item_code.gst_hsn_code, a column india_compliance adds — so on a bench
		without it every insert died with `Unknown column 'gst_hsn_code'`.
		"""
		ours = {(cf.get("dt"), cf.get("fieldname")) for cf in self.fields}

		def is_standard(doctype, fieldname):
			return bool(
				frappe.get_all(
					"DocField",
					filters={"parent": doctype, "fieldname": fieldname},
					limit=1,
				)
			)

		strangers = []
		for cf in self.fields:
			fetch_from = (cf.get("fetch_from") or "").strip()
			if not fetch_from or "." not in fetch_from:
				continue
			dt = cf.get("dt")
			link_fieldname, _, source_fieldname = fetch_from.partition(".")

			link_options = None
			if is_standard(dt, link_fieldname):
				link_options = frappe.db.get_value(
					"DocField", {"parent": dt, "fieldname": link_fieldname}, "options"
				)
			elif (dt, link_fieldname) in ours:
				link_options = next(
					c.get("options")
					for c in self.fields
					if (c.get("dt"), c.get("fieldname")) == (dt, link_fieldname)
				)
			else:
				strangers.append(
					f"{dt}.{cf.get('fieldname')} fetches through {link_fieldname}, which is nobody's"
				)
				continue

			if (
				not is_standard(link_options, source_fieldname)
				and (link_options, source_fieldname) not in ours
			):
				strangers.append(
					f"{dt}.{cf.get('fieldname')} reads {link_options}.{source_fieldname}, "
					"a column this bench may not have"
				)

		self.assertEqual(strangers, [], "; ".join(strangers))
