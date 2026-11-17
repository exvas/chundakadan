"""An approval email that cannot be sent must never take the document with it."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.chundakadan.api import approval_email

NO_ACCOUNT = "Please setup default outgoing Email Account from Tools > Email Account"


class TestAnEmailThatCannotBeSent(FrappeTestCase):
	"""2026-11-17: outgoing mail was switched off on the live site, and from
	then on nobody could save a Leave Application -- or anything else that
	mails its approver. The send failed, which is fine and was caught; the
	handler then logged it with the whole sentence as the Error Log *title*,
	which holds 140 characters, so the logging itself threw from inside the
	except block and the save was rolled back."""

	def setUp(self):
		frappe.set_user("Administrator")
		self.doc = frappe.get_doc(
			{
				"doctype": "Leave Application",
				"name": "LAP-CA-26-0666",
				"employee_name": "Bindu T",
				"current_approver": "sales@chundakadan.in",
			}
		)
		frappe.clear_messages()

	def _send_with_mail_switched_off(self):
		def refuse(*args, **kwargs):
			frappe.throw(NO_ACCOUNT, frappe.OutgoingEmailError)

		with patch.object(frappe, "sendmail", side_effect=refuse):
			approval_email.send_approval_email(self.doc, "created", "sales@chundakadan.in")

	def test_the_document_survives(self):
		self._send_with_mail_switched_off()  # must not raise

	def test_it_is_logged_under_a_title_that_fits(self):
		before = frappe.db.count("Error Log")
		self._send_with_mail_switched_off()
		self.assertEqual(frappe.db.count("Error Log"), before + 1)
		title, error = frappe.db.get_value("Error Log", {}, ["method", "error"], order_by="creation desc")
		self.assertLessEqual(len(title), 140)
		self.assertIn("LAP-CA-26-0666", error, "the detail belongs in the body")

	def test_the_user_is_not_shown_a_mail_server_message(self):
		"""They saved a leave. Whether the office has an outgoing mail
		account is not something to put in front of them."""
		self._send_with_mail_switched_off()
		shown = " ".join(str(m) for m in frappe.get_message_log())
		self.assertNotIn("Email Account", shown)

	def test_a_very_long_failure_still_cannot_break_the_log(self):
		def refuse(*args, **kwargs):
			raise RuntimeError("x" * 2000)

		with patch.object(frappe, "sendmail", side_effect=refuse):
			approval_email.send_approval_email(self.doc, "created", "sales@chundakadan.in")
