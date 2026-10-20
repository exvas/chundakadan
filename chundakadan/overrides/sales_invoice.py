"""Standalone credit notes: cost the returned goods from the Item master.

A credit note that is not linked to an original invoice (``return_against``
empty) brings stock back in, so ERPNext has to decide what that stock cost.
It looks only at the Stock Ledger, on purpose: ``selling_controller.py`` calls
``get_incoming_rate(..., fallbacks=not is_standalone)``, which switches the
Item master / Item Price fallbacks **off** for a standalone return.

So for an item with no ledger history before the return's posting date there
is no cost to be found, and ERPNext stops with "Valuation Rate for the Item
{0}, is required ..." — a message that then advises mentioning the valuation
rate in the Item master, which that same code has just refused to read. That
is the state the business keeps hitting: goods sold before the ERP went live
come back on a credit note, and the item they are on has no earlier movement.

Where ERPNext finds no cost in the ledger this override uses the Item master's
Valuation Rate (then Standard Rate), which is what the dialog told the user to
set. Two behaviours change, both deliberately:

  * the stop becomes a posting at the Item master rate;
  * where ERPNext would have fallen back to ``d.rate`` — the *selling* price —
    the item's own cost is used instead, so a return can no longer inflate the
    value of stock.

Rows ERPNext *can* price from the ledger are never touched, and a row whose
item carries no rate at all still stops, because that one needs a human.
"""

import frappe
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from frappe.utils import flt


def fallback_rate(item_code: str) -> float:
	"""The Item master's own idea of what one unit costs."""
	item = frappe.get_cached_value("Item", item_code, ["valuation_rate", "standard_rate"], as_dict=1)
	if not item:
		return 0.0
	return flt(item.valuation_rate) or flt(item.standard_rate)


def is_standalone_return(doc) -> bool:
	return bool(doc.get("is_return") and not doc.get("return_against") and doc.get("update_stock"))


def hold_rows(doc) -> list:
	"""Let ERPNext price the rows without stopping, and remember what it was told.

	Setting ``allow_zero_valuation_rate`` keeps ERPNext from throwing when the
	ledger has no rate, and from substituting the selling rate; both cases then
	arrive at :func:`release_rows` as an incoming rate of zero. The original
	value of the field is handed back so nothing of the user's is overwritten.
	"""
	if not is_standalone_return(doc):
		return []

	held = []
	for row in doc.get("items") or []:
		if row.get("allow_zero_valuation_rate"):
			continue  # the user asked for a zero cost: that is their call
		if not frappe.get_cached_value("Item", row.item_code, "is_stock_item"):
			continue
		rate = fallback_rate(row.item_code)
		if not rate:
			continue  # no cost anywhere: let ERPNext stop, a human must decide
		held.append((row, rate))
		row.allow_zero_valuation_rate = 1
	return held


def release_rows(held) -> None:
	"""Put the flag back, and fill in the cost ERPNext could not find."""
	for row, rate in held:
		row.allow_zero_valuation_rate = 0
		if not flt(row.get("incoming_rate")):
			row.incoming_rate = rate


class CustomSalesInvoice(SalesInvoice):
	def set_incoming_rate(self):
		held = hold_rows(self)
		try:
			super().set_incoming_rate()
		finally:
			release_rows(held)
