"""Site setup for dispatch tracking: role, Sales Invoice field, permissions.

ensure_dispatch_role runs in before_migrate so the role exists before the
Dispatch Log DocType and Dispatch page (which reference it) are synced.
ensure_dispatch_setup runs in after_migrate. Both are idempotent.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission

from chundakadan.dispatch import constants as C

# Doctypes a Dispatch User must be able to read from the Dispatch page:
# open the invoice, pick a transporter, see the customer.
DISPATCH_READ_DOCTYPES = ("Sales Invoice", "Supplier", "Customer")


def ensure_dispatch_role(*args, **kwargs):
	if frappe.db.exists("Role", C.ROLE):
		return
	frappe.get_doc({"doctype": "Role", "role_name": C.ROLE, "desk_access": 1}).insert(
		ignore_permissions=True
	)


def ensure_sales_invoice_field():
	create_custom_fields(
		{
			"Sales Invoice": [
				{
					"fieldname": "dispatch_status",
					"label": "Dispatch Status",
					"fieldtype": "Data",
					"insert_after": "transporter_info",
					"read_only": 1,
					"allow_on_submit": 1,
					"no_copy": 1,
					"in_list_view": 1,
					"in_standard_filter": 1,
					"module": "Chundakadan",
				}
			]
		},
		update=True,
	)


def ensure_dispatch_permissions():
	# add_permission copies the standard DocPerms into Custom DocPerm first,
	# so existing roles keep their access.
	for doctype in DISPATCH_READ_DOCTYPES:
		if frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": C.ROLE, "permlevel": 0}):
			continue
		add_permission(doctype, C.ROLE, 0)
		frappe.clear_cache(doctype=doctype)


def ensure_dispatch_setup(*args, **kwargs):
	ensure_dispatch_role()
	ensure_sales_invoice_field()
	ensure_dispatch_permissions()
	frappe.db.commit()
