"""General Ledger: stop the Voucher Type column pointing at DocType.

erpnext 15.124 turned the report's Voucher Type column into a Link to
``DocType``::

    {"label": _("Voucher Type"), "fieldname": "voucher_type",
     "fieldtype": "Link", "options": "DocType", "width": 120}

Frappe then counts ``DocType`` among the report's linked doctypes and, in
``query_report.get_filtered_data`` → ``get_user_match_filters`` →
``build_match_conditions``, asks whether the reader may read it. Only System
Manager and Administrator ever may — that is stock Frappe, not a setting
anyone here got wrong — so every other user opening the General Ledger is
stopped with::

    frappe.exceptions.PermissionError: No permission to read DocType

Nothing is wrong with their own permissions, and the message names a doctype
they never asked for, so there is nothing for them to act on.

Upstream has already changed the column to a plain ``Select`` on
version-15-hotfix, which is what this does: the same change, applied until
that release reaches the site. Once it does, the column arrives as a Select
already and this simply finds nothing to fix.
"""

import frappe


def fix_voucher_type_column(columns):
	"""Make the Voucher Type column stop being a link to DocType."""
	for column in columns or []:
		if not isinstance(column, dict):
			continue
		if column.get("fieldname") != "voucher_type":
			continue
		if column.get("fieldtype") == "Link" and column.get("options") == "DocType":
			column["fieldtype"] = "Select"
			column.pop("options", None)
	return columns


def install():
	from erpnext.accounts.report.general_ledger import general_ledger

	if getattr(general_ledger.get_columns, "_cdn_gl_voucher_type", False):
		return  # already patched in this interpreter

	orig = general_ledger.get_columns

	def get_columns(filters):
		return fix_voucher_type_column(orig(filters))

	get_columns._cdn_gl_voucher_type = True
	general_ledger.get_columns = get_columns
