import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate

from chundakadan.doc_events.purchase_invoice import refresh_payment_schedule

COMPANY = "Chundakadan Agencies"


class TestPurchaseInvoicePaymentSchedule(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# this dev copy has never run migrate, so seed the settings fields
		from chundakadan.doc_events.stock_control import ensure_update_stock_settings

		ensure_update_stock_settings()
		self.template = frappe.db.get_value("Payment Terms Template", {"name": "45 Days"}, "name") or frappe.db.get_value("Payment Terms Template", {}, "name")
		if not self.template:
			self.skipTest("no payment terms template")
		self.term = frappe.get_doc("Payment Terms Template", self.template).terms[0].payment_term
		self.credit_days = frappe.db.get_value("Payment Term", self.term, "credit_days")

	def tearDown(self):
		frappe.db.rollback()

	def _invoice(self, bill_date=None):
		supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
		item = frappe.db.get_value("Item", {"is_stock_item": 1, "disabled": 0, "has_variants": 0}, "name")
		doc = frappe.get_doc({
			"doctype": "Purchase Invoice",
			"supplier": supplier,
			"company": COMPANY,
			"posting_date": nowdate(),
			"set_posting_time": 1,
			"bill_no": frappe.generate_hash(length=6),
			"bill_date": bill_date,
			"payment_terms_template": self.template,
			"items": [{"item_code": item, "qty": 1, "rate": 1000, "warehouse": frappe.db.get_value("Warehouse", {"company": COMPANY, "is_group": 0}, "name")}],
		})
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		return doc

	def test_due_date_follows_the_supplier_invoice_date(self):
		doc = self._invoice(bill_date=add_days(nowdate(), -8))
		expected = add_days(doc.bill_date, self.credit_days)
		self.assertEqual(getdate(doc.payment_schedule[0].due_date), getdate(expected))
		self.assertEqual(getdate(doc.due_date), getdate(expected))

	def test_changing_the_supplier_invoice_date_moves_the_due_date(self):
		doc = self._invoice(bill_date=add_days(nowdate(), -8))
		old_due = getdate(doc.due_date)
		doc.bill_date = nowdate()
		doc.save()
		doc.reload()
		expected = getdate(add_days(nowdate(), self.credit_days))
		self.assertNotEqual(getdate(doc.payment_schedule[0].due_date), old_due)
		self.assertEqual(getdate(doc.payment_schedule[0].due_date), expected)
		self.assertEqual(getdate(doc.due_date), expected)

	def test_changing_the_posting_date_moves_the_due_date_when_no_bill_date(self):
		doc = self._invoice()
		doc.posting_date = add_days(nowdate(), 3)
		doc.save()
		doc.reload()
		expected = getdate(add_days(add_days(nowdate(), 3), self.credit_days))
		self.assertEqual(getdate(doc.payment_schedule[0].due_date), expected)
		self.assertEqual(getdate(doc.due_date), expected)

	def test_submitted_invoice_is_left_alone(self):
		doc = self._invoice(bill_date=add_days(nowdate(), -8))
		doc.docstatus = 1
		before = doc.payment_schedule[0].due_date
		doc.bill_date = nowdate()
		refresh_payment_schedule(doc)
		self.assertEqual(doc.payment_schedule[0].due_date, before)

	def test_changing_the_template_rebuilds_the_schedule(self):
		# a short template of our own: an arbitrary existing one can exceed
		# the supplier's allowed credit days and fail validation
		term = frappe.get_doc({
			"doctype": "Payment Term",
			"payment_term_name": f"Test 7 Days {frappe.generate_hash(length=4)}",
			"due_date_based_on": "Day(s) after invoice date",
			"credit_days": 7,
			"invoice_portion": 100,
		}).insert()
		other = frappe.get_doc({
			"doctype": "Payment Terms Template",
			"template_name": f"Test 7 Days {frappe.generate_hash(length=4)}",
			"terms": [{"payment_term": term.name, "invoice_portion": 100, "credit_days": 7, "due_date_based_on": "Day(s) after invoice date"}],
		}).insert().name
		doc = self._invoice(bill_date=nowdate())
		doc.payment_terms_template = other
		doc.save()
		doc.reload()
		expected_terms = [row.payment_term for row in frappe.get_doc("Payment Terms Template", other).terms]
		self.assertEqual([row.payment_term for row in doc.payment_schedule], expected_terms)
		self.assertEqual(getdate(doc.due_date), max(getdate(row.due_date) for row in doc.payment_schedule))
