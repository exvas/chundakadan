import frappe
from frappe.utils import getdate

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


def refresh_payment_schedule(doc, method=None):
	"""Keep the Payment Schedule (and Due Date) in step with the invoice dates.

	ERPNext builds the schedule only when it is empty, so once a row exists,
	changing the Supplier Invoice Date or Posting Date leaves the old due
	date behind. Re-derive each row's date from its own payment term, then
	let the due date follow the schedule.
	"""
	if doc.docstatus != 0 or not doc.get("payment_schedule"):
		return
	base_date = doc.get("bill_date") or doc.get("posting_date")
	if not base_date:
		return

	from erpnext.controllers.accounts_controller import get_discount_date, get_due_date, get_payment_terms

	# Template swapped after the rows were made? Rebuild from the template.
	if doc.get("payment_terms_template"):
		template_terms = [
			row.payment_term
			for row in frappe.get_cached_doc("Payment Terms Template", doc.payment_terms_template).terms
		]
		if [row.payment_term for row in doc.payment_schedule] != template_terms:
			doc.set(
				"payment_schedule",
				get_payment_terms(
					doc.payment_terms_template,
					doc.posting_date,
					doc.get("grand_total"),
					doc.get("base_grand_total"),
					doc.get("bill_date"),
				),
			)
			doc.set_due_date()
			return

	changed = False
	for row in doc.payment_schedule:
		if not row.payment_term:
			continue
		term = frappe.get_cached_doc("Payment Term", row.payment_term)
		due_date = get_due_date(term, bill_date=base_date)
		if due_date and getdate(row.due_date) != getdate(due_date):
			row.due_date = due_date
			changed = True
		discount_date = get_discount_date(term, bill_date=base_date)
		if discount_date:
			row.discount_date = discount_date
	if changed:
		doc.set_due_date()
