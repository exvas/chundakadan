"""Take the Billing Verification step out of the Purchase Order chain.

The accountant who held `PO Billing Coordinator` moved up to the Accounts
Manager post, which left that step with nobody who could take it, and
every purchase order stopped there -- PO-CA-26-0016 among them. A step
no one can take is not a control, it is a wall.

So "Send for Verification" now goes straight to Sales Verification. The
old state is kept, and its two transitions handed to the Deputy Sales
Manager, so an order already parked there can be moved on rather than
stranded a second time.

The workflow is seeded create-if-missing, so that edits made in the UI
survive an app update -- which means a change to the spec never reaches
a site that already has the workflow. This carries it across, once.
"""

import frappe

from chundakadan.seed.po_workflow import BILLING, SALES, SALES_ROLE, WORKFLOW


def execute():
	if not frappe.db.exists("Workflow", WORKFLOW):
		return

	workflow = frappe.get_doc("Workflow", WORKFLOW)
	changed = False

	for row in workflow.transitions:
		if row.state == "Draft" and row.action == "Send for Verification" and row.next_state == BILLING:
			row.next_state = SALES
			changed = True
		elif row.state == BILLING and row.allowed != SALES_ROLE:
			row.allowed = SALES_ROLE
			changed = True

	for row in workflow.states:
		if row.state == BILLING and row.allow_edit != SALES_ROLE:
			row.allow_edit = SALES_ROLE
			changed = True

	if changed:
		workflow.save(ignore_permissions=True)

	# and move the orders that are already stuck there
	stuck = frappe.db.get_all(
		"Purchase Order",
		filters={"workflow_state": BILLING, "docstatus": 0},
		pluck="name",
	)
	for name in stuck:
		frappe.db.set_value("Purchase Order", name, "workflow_state", SALES, update_modified=False)
	if stuck:
		frappe.logger().info(f"drop_po_billing_step: moved {len(stuck)} order(s) on: {stuck}")
