import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.doc_events.address_gst import set_state_from_gstin, state_for_gstin


class TestAddressGST(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_state_for_gstin(self):
		self.assertEqual(state_for_gstin("32AAGFC3363E1ZX"), "Kerala")
		self.assertEqual(state_for_gstin("34ADIPV1804A1ZZ"), "Puducherry")
		self.assertEqual(state_for_gstin("29ABCDE1234F1Z5"), "Karnataka")

	def test_unknown_or_empty_gstin(self):
		self.assertIsNone(state_for_gstin(""))
		self.assertIsNone(state_for_gstin(None))
		self.assertIsNone(state_for_gstin("ABCDE1234F1Z5"))
		self.assertIsNone(state_for_gstin("99ABCDE1234F1Z5"))

	def _address(self, **values):
		doc = frappe.get_doc({
			"doctype": "Address",
			"address_title": f"GST Test {frappe.generate_hash(length=5)}",
			"address_type": "Billing",
			"address_line1": "Test line",
			"city": "Test",
			"country": "India",
			"state": "Kerala",
			"pincode": "673310",
			**values,
		})
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		return doc

	def test_set_state_from_gstin_moves_the_address(self):
		doc = self._address()
		frappe.db.set_value("Address", doc.name, "gstin", "34ADIPV1804A1ZZ")
		result = set_state_from_gstin(doc.name)
		self.assertEqual(result, {"state": "Puducherry", "changed": True})
		self.assertEqual(frappe.db.get_value("Address", doc.name, "state"), "Puducherry")
		self.assertEqual(frappe.db.get_value("Address", doc.name, "gst_state_number"), "34")

	def test_no_change_when_it_already_matches(self):
		doc = self._address(state="Kerala")
		frappe.db.set_value("Address", doc.name, "gstin", "32AAGFC3363E1ZX")
		self.assertEqual(set_state_from_gstin(doc.name), {"state": "Kerala", "changed": False})

	def test_unknown_code_is_refused(self):
		doc = self._address()
		frappe.db.set_value("Address", doc.name, "gstin", "99ABCDE1234F1Z5")
		with self.assertRaises(frappe.ValidationError):
			set_state_from_gstin(doc.name)
