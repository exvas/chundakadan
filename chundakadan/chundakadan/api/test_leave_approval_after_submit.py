"""Approving an already-submitted Leave Application must update the chain rows."""

from unittest import SkipTest

import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.chundakadan.api import leave as leave_api
from chundakadan.patches import allow_leave_chain_updates as chain_patch

test_ignore = ["Leave Application", "Employee", "User", "Company"]
CHILD = "Leave Approval Detail"


def submitted_pending_leave():
	rows = frappe.db.sql(
		"""select la.name from `tabLeave Application` la
		join `tabLeave Approval Detail` d on d.parent = la.name
		where la.docstatus = 1 and la.custom_approval_status = %s and d.idx = 1 and d.status = %s
		order by la.modified desc limit 1""",
		("Pending", "Pending"),
	)
	if not rows:
		raise SkipTest("no submitted, pending Leave Application on this site")
	return rows[0][0]


def clear_chain_property_setters():
	frappe.db.delete(
		"Property Setter",
		{"doc_type": CHILD, "property": "allow_on_submit", "field_name": ["in", list(chain_patch.CHAIN_FIELDS)]},
	)
	frappe.clear_cache(doctype=CHILD)


class TestLeaveApprovalAfterSubmit(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		frappe.flags.mute_emails = True

	def setUp(self):
		clear_chain_property_setters()

	def tearDown(self):
		frappe.clear_cache(doctype=CHILD)

	def test_chain_row_is_blocked_without_the_patch(self):
		name = submitted_pending_leave()
		with self.assertRaises(frappe.ValidationError) as caught:
			leave_api.approve_leave(name)
		self.assertIn("after submission", str(caught.exception))

	def test_patch_marks_every_chain_field_allow_on_submit(self):
		chain_patch.execute()
		meta = frappe.get_meta(CHILD, cached=False)
		for fieldname in chain_patch.CHAIN_FIELDS:
			self.assertTrue(meta.get_field(fieldname).allow_on_submit, f"{fieldname} still blocked")

	def test_approval_updates_the_chain_after_the_patch(self):
		name = submitted_pending_leave()
		chain_patch.execute()
		leave_api.approve_leave(name)
		row = frappe.db.get_value(CHILD, {"parent": name, "idx": 1}, ["status", "approved_on"], as_dict=True)
		self.assertEqual(row.status, "Approved")
		self.assertIsNotNone(row.approved_on)
		self.assertIn(
			frappe.db.get_value("Leave Application", name, "custom_approval_status"),
			("Partially Approved", "Approved"),
		)

	def test_patch_is_idempotent(self):
		chain_patch.execute()
		chain_patch.execute()
		self.assertEqual(
			frappe.db.count(
				"Property Setter",
				{"doc_type": CHILD, "property": "allow_on_submit", "field_name": "status"},
			),
			1,
		)
