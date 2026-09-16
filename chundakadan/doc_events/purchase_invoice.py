import frappe

from chundakadan.doc_events.sales_invoice import COMPANY_STORE_WAREHOUSE
from chundakadan.doc_events.stock_control import get_update_stock


def apply_stock_defaults(doc, method=None):
	"""before_validate on Purchase Invoice: tick Update Stock and set the company's
	Stores warehouse as Set Accepted Warehouse and on item rows.

	Skipped for opening invoices, subcontracted invoices, and invoices made
	against a Purchase Receipt (stock already received by the PR)."""
	if doc.docstatus != 0 or doc.get("is_opening") == "Yes" or doc.get("is_subcontracted"):
		return
	if any(row.get("purchase_receipt") or row.get("pr_detail") for row in doc.get("items") or []):
		return

	warehouse = COMPANY_STORE_WAREHOUSE.get(doc.company)
	if not warehouse or not frappe.db.exists("Warehouse", warehouse):
		return

	doc.update_stock = get_update_stock("Purchase Invoice")

	def belongs_to_company(wh):
		return wh and frappe.get_cached_value("Warehouse", wh, "company") == doc.company

	if not belongs_to_company(doc.get("set_warehouse")):
		doc.set_warehouse = warehouse
	for row in doc.get("items") or []:
		if not belongs_to_company(row.get("warehouse")):
			row.warehouse = doc.set_warehouse
