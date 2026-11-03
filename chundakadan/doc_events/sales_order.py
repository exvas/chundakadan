import frappe
from frappe import _
from frappe.utils import flt, get_link_to_form


@frappe.whitelist()
def validate_item_qty_in_stock(doc, method=None):
	if not doc.custom_special_order:
		for item in doc.items:
			if item.item_code and item.warehouse:
				available_qty = flt(
					frappe.get_value(
						"Bin", {"item_code": item.item_code, "warehouse": item.warehouse}, "actual_qty"
					)
				)
				if available_qty < item.qty:
					frappe.throw(
						f"Item {item.item_code} in warehouse {item.warehouse}: "
						f"Only {available_qty} available, but {item.qty} required.",
						title="Insufficient Stock",
					)


def refuse_cancel_when_billed_or_delivered(doc, method=None):
	"""A Sales Order cannot be cancelled once it has been invoiced or delivered.

	ERPNext only stops this while the invoice is still a draft
	(``check_nextdoc_docstatus`` looks for ``docstatus = 0``), so an order
	that has been billed and sent could still be cancelled. The invoice then
	cannot be cancelled either: cancelling it updates the order's reserved
	quantity, and that refuses to touch a cancelled order — "Sales Order X is
	cancelled or closed". The pair is stuck, one cancelled and one not, with
	nothing in the UI to say why.

	So the order is held instead. Cancel the invoice first (and the delivery
	note), then the order, which is the order the documents were made in.
	"""
	blocking = _submitted_documents_against(doc.name)
	if not blocking:
		return

	listed = "<br>".join(f"{_(kind)} {get_link_to_form(kind, name)}" for kind, name in blocking)
	frappe.throw(
		_("This order has already been billed or delivered:")
		+ f"<br><br>{listed}<br><br>"
		+ _("Cancel those first, then this order."),
		title=_("Cannot cancel this Sales Order"),
	)


def _submitted_documents_against(sales_order):
	"""Submitted invoices and delivery notes that name this order."""
	found = []
	for name in frappe.db.sql_list(
		"""select distinct si.name from `tabSales Invoice` si
		   join `tabSales Invoice Item` sii on sii.parent = si.name
		  where sii.sales_order = %s and si.docstatus = 1""",
		sales_order,
	):
		found.append(("Sales Invoice", name))
	for name in frappe.db.sql_list(
		"""select distinct dn.name from `tabDelivery Note` dn
		   join `tabDelivery Note Item` dni on dni.parent = dn.name
		  where dni.against_sales_order = %s and dn.docstatus = 1""",
		sales_order,
	):
		found.append(("Delivery Note", name))
	return found
