import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from chundakadan.chundakadan.doctype.post_dated_cheque.post_dated_cheque import (
	PE_FIELD,
	collect,
	ensure_payment_entry_field,
	mark_returned,
)
from chundakadan.patches.backfill_pdc_payment_links import execute

COMPANY = "Chundakadan Agencies"


class TestBackfillPDCPaymentLinks(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("DocType", "Post Dated Cheque"):
			self.skipTest("Post Dated Cheque not installed")
		ensure_payment_entry_field()
		invoice = frappe.get_all(
			"Sales Invoice",
			filters={"docstatus": 1, "company": COMPANY, "outstanding_amount": [">", 0]},
			fields=["customer"],
			limit=1,
		)
		if not invoice:
			self.skipTest("no customer with outstanding")
		self.customer = invoice[0].customer

	def tearDown(self):
		frappe.db.rollback()

	def test_links_both_payments_back_to_the_cheque(self):
		doc = frappe.get_doc({
			"doctype": "Post Dated Cheque",
			"company": COMPANY,
			"customer": self.customer,
			"posting_date": nowdate(),
			"cheque_no": frappe.generate_hash(length=8),
			"cheque_date": add_days(nowdate(), 5),
			"amount": 500,
			"sales_person": frappe.db.get_value("Sales Person", {"enabled": 1}, "name"),
		})
		doc.insert()
		doc.submit()
		collect(doc.name, posting_date=nowdate())
		doc.reload()
		result = mark_returned(doc.name, reason="Returned")
		doc.reload()

		# pretend they were made before the field existed
		for payment in (doc.payment_entry, result["return_payment_entry"]):
			frappe.db.set_value("Payment Entry", payment, PE_FIELD, None, update_modified=False)

		execute()

		for payment in (doc.payment_entry, result["return_payment_entry"]):
			self.assertEqual(frappe.db.get_value("Payment Entry", payment, PE_FIELD), doc.name)

	def test_runs_twice_without_complaint(self):
		execute()
		execute()
