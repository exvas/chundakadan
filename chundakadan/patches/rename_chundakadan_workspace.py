import frappe

OLD = "Chundakadan"
NEW = "Sales Order Queue"


def execute():
	"""Rename the Chundakadan workspace to Sales Order Queue.

	Runs **before** the model sync so the workspace file (now shipped as
	sales_order_queue) updates the renamed record instead of creating a
	second one. Safe to run on a site that has neither or already has the
	new name; anything the site added to the workspace travels with it,
	because the record is renamed rather than rebuilt.
	"""
	if not frappe.db.exists("Workspace", OLD):
		return

	if frappe.db.exists("Workspace", NEW):
		# both present (e.g. the file landed first) — keep the new one
		frappe.delete_doc("Workspace", OLD, ignore_permissions=True, force=True)
		return

	frappe.rename_doc("Workspace", OLD, NEW, force=True)
	frappe.db.set_value("Workspace", NEW, {"title": NEW, "label": NEW})
