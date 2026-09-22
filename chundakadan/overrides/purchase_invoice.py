"""Purchase Invoice: credit days run from the posting date.

ERPNext counts a supplier's credit period from the Supplier Invoice Date
when one is entered (bill_date), falling back to the posting date. Here the
business counts it from the **posting date** — the day the bill is entered —
so both the schedule and ERPNext's own due-date check have to use that.
"""

from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice
from erpnext.accounts.party import validate_due_date


class CustomPurchaseInvoice(PurchaseInvoice):
	def validate_due_date(self):
		if self.get("is_pos"):
			return
		# bill_date deliberately not passed: the credit period starts on the
		# posting date, so the allowed due date must be measured from it too
		validate_due_date(
			self.posting_date, self.due_date, None, self.payment_terms_template, self.doctype
		)
