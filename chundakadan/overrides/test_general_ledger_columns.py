"""The General Ledger must open for someone who is not a System Manager."""

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.overrides.general_ledger_columns import fix_voucher_type_column, install

# the shape erpnext 15.124 ships, which is what stops ordinary users
BROKEN = {
	"label": "Voucher Type",
	"fieldname": "voucher_type",
	"fieldtype": "Link",
	"options": "DocType",
	"width": 120,
}


class TestGeneralLedgerColumns(FrappeTestCase):
	def test_the_voucher_type_column_stops_linking_to_doctype(self):
		columns = fix_voucher_type_column([dict(BROKEN)])
		self.assertEqual(columns[0]["fieldtype"], "Select")
		self.assertNotIn("options", columns[0], "a Select with DocType options still links")

	def test_the_label_and_width_are_left_as_they_are(self):
		columns = fix_voucher_type_column([dict(BROKEN)])
		self.assertEqual(columns[0]["label"], "Voucher Type")
		self.assertEqual(columns[0]["width"], 120)

	def test_other_links_are_not_touched(self):
		account = {"fieldname": "account", "fieldtype": "Link", "options": "Account"}
		gl = {"fieldname": "gl_entry", "fieldtype": "Link", "options": "GL Entry"}
		fix_voucher_type_column([account, gl])
		self.assertEqual(account["options"], "Account", "the Account link is wanted and allowed")
		self.assertEqual(gl["options"], "GL Entry")

	def test_a_column_already_fixed_upstream_is_left_alone(self):
		"""Once the release lands, the column arrives as a Select already."""
		fixed = {"fieldname": "voucher_type", "fieldtype": "Select", "width": 120}
		columns = fix_voucher_type_column([dict(fixed)])
		self.assertEqual(columns[0], fixed)

	def test_string_columns_do_not_break_it(self):
		self.assertEqual(fix_voucher_type_column(["Label:Data:120"]), ["Label:Data:120"])

	def test_the_report_itself_never_links_to_doctype_once_installed(self):
		install()
		from erpnext.accounts.report.general_ledger.general_ledger import get_columns

		columns = get_columns(frappe._dict({"company": frappe.defaults.get_user_default("Company")}))
		offenders = [
			c.get("fieldname")
			for c in columns
			if isinstance(c, dict) and c.get("fieldtype") == "Link" and c.get("options") == "DocType"
		]
		self.assertEqual(offenders, [], "a Link to DocType stops every non-System-Manager")
