import os

import frappe
from frappe.modules.import_file import import_file_by_path
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from chundakadan.chundakadan.api import work_summary as ws

HOD_ROLE = "Sales HOD Leave Approver"
GM_ROLE = "GM Leave Approver"
EMP_USER = "dws.employee@example.com"
HOD_USER = "dws.hod@example.com"
GM_USER = "dws.gm@example.com"
OTHER_USER = "dws.other@example.com"


def _import(*parts):
	import_file_by_path(
		os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts), force=True
	)


class WorkSummaryCase(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# the dev copy has never migrated, so pull the two doctypes in
		base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
		import_file_by_path(
			os.path.join(base, "daily_work_summary_task", "daily_work_summary_task.json"), force=True
		)
		_import("daily_work_summary.json")
		frappe.db.commit()

	def setUp(self):
		frappe.set_user("Administrator")
		self.company = frappe.db.get_value("Company", {}, "name")
		self.employee = self._employee(EMP_USER, "Sales& Marketing - CA")
		self._user(HOD_USER, [HOD_ROLE])
		self._user(GM_USER, [GM_ROLE])
		# user_for_role prefers a role holder with an active Employee, so on
		# a real site it picks the actual HOD / GM. Test against that.
		self.hod = ws.user_for_role(HOD_ROLE)
		self.gm = ws.user_for_role(GM_ROLE)
		self._user(OTHER_USER, ["Employee"])
		self._clear_previous()

	def _clear_previous(self):
		"""Sending a summary fires a push, which commits, so documents
		survive the per-test rollback. Start each test with a clean slate."""
		for name in frappe.get_all(
			"Daily Work Summary", filters={"employee": self.employee}, pluck="name"
		):
			frappe.db.delete("Daily Work Summary Task", {"parent": name})
			frappe.db.delete("Chundakadan Approval Detail", {"parent": name})
			frappe.db.delete("Daily Work Summary", {"name": name})
		frappe.db.commit()

	def tearDown(self):
		frappe.set_user("Administrator")

	# -- fixtures ---------------------------------------------------------

	def _user(self, email, roles):
		if not frappe.db.exists("User", email):
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": email.split("@")[0],
				"send_welcome_email": 0, "user_type": "System User",
			}).insert(ignore_permissions=True)
		frappe.get_doc("User", email).add_roles("Employee", *roles)
		return email

	def _employee(self, email, department):
		self._user(email, [])
		existing = frappe.db.get_value("Employee", {"user_id": email}, "name")
		if existing:
			return existing
		dept = department if frappe.db.exists("Department", department) else frappe.db.get_value("Department", {}, "name")
		doc = frappe.get_doc({
			"doctype": "Employee",
			"first_name": "DWS Tester",
			"user_id": email,
			"company": frappe.db.get_value("Company", {}, "name"),
			"date_of_birth": "1995-01-01",
			"date_of_joining": "2026-01-01",
			"gender": frappe.db.get_value("Gender", {}, "name"),
			"status": "Active",
			"department": dept,
		}).insert(ignore_permissions=True)
		return doc.name

	def _summary(self, work_date=None, as_user=EMP_USER, tasks=None):
		frappe.set_user(as_user)
		doc = frappe.get_doc({
			"doctype": "Daily Work Summary",
			"employee": self.employee,
			"company": self.company,
			"work_date": work_date or today(),
			"tasks": tasks or [
				{"task": "Customer visit", "work_description": "4 shops in Calicut"},
				{"task": "Payment follow-up", "work_description": "3 parties called"},
			],
		}).insert(ignore_permissions=True)
		frappe.set_user("Administrator")
		return doc

	def _send(self, doc):
		frappe.set_user(EMP_USER)
		ws.send_for_remarks(doc.name)
		frappe.set_user("Administrator")
		doc.reload()
		return doc


class TestTheChain(WorkSummaryCase):
	def test_a_new_summary_starts_as_a_draft(self):
		doc = self._summary()
		self.assertEqual(doc.custom_approval_status, ws.STATUS_DRAFT)
		self.assertFalse(doc.current_approver)
		self.assertEqual(doc.department, frappe.db.get_value("Employee", self.employee, "department"))

	def test_sending_puts_it_in_front_of_the_hod(self):
		doc = self._send(self._summary())
		self.assertEqual(doc.custom_approval_status, ws.STATUS_PENDING)
		self.assertEqual(doc.current_approver, self.hod)
		self.assertEqual([r.approver_role for r in doc.approval_flow], [HOD_ROLE, GM_ROLE])

	def test_the_hod_remark_passes_it_to_the_gm(self):
		doc = self._send(self._summary())
		frappe.set_user(self.hod)
		result = ws.add_remarks(doc.name, "Good coverage, push the Calicut orders")
		frappe.set_user("Administrator")
		doc.reload()
		self.assertEqual(result["status"], ws.STATUS_PARTIAL)
		self.assertEqual(doc.hod_remarks, "Good coverage, push the Calicut orders")
		self.assertEqual(doc.current_approver, self.gm)
		self.assertEqual(doc.docstatus, 0)

	def test_the_gm_remark_closes_and_submits_it(self):
		doc = self._send(self._summary())
		frappe.set_user(self.hod)
		ws.add_remarks(doc.name, "HOD ok")
		frappe.set_user(self.gm)
		ws.add_remarks(doc.name, "Noted")
		frappe.set_user("Administrator")
		doc.reload()
		self.assertEqual(doc.custom_approval_status, ws.STATUS_APPROVED)
		self.assertEqual(doc.gm_remarks, "Noted")
		self.assertEqual(doc.hod_remarks, "HOD ok")
		self.assertIsNone(doc.current_approver)
		self.assertEqual(doc.docstatus, 1)

	def test_each_step_is_stamped_in_the_flow(self):
		doc = self._send(self._summary())
		frappe.set_user(self.hod)
		ws.add_remarks(doc.name, "HOD ok")
		frappe.set_user("Administrator")
		doc.reload()
		row = doc.approval_flow[0]
		self.assertEqual(row.status, "Approved")
		self.assertEqual(row.approver, self.hod)
		self.assertEqual(row.remarks, "HOD ok")
		self.assertTrue(row.approved_on)

	def test_a_remark_is_required_to_move_it_on(self):
		doc = self._send(self._summary())
		frappe.set_user(self.hod)
		for blank in ("", "   ", None):
			with self.assertRaises(frappe.ValidationError):
				ws.add_remarks(doc.name, blank)
		frappe.set_user("Administrator")
		doc.reload()
		self.assertEqual(doc.custom_approval_status, ws.STATUS_PENDING)

	def test_a_closed_summary_cannot_be_moved_again(self):
		doc = self._send(self._summary())
		frappe.set_user(self.hod)
		ws.add_remarks(doc.name, "ok")
		frappe.set_user(self.gm)
		ws.add_remarks(doc.name, "closed")
		with self.assertRaises(frappe.ValidationError):
			ws.add_remarks(doc.name, "again")
		frappe.set_user("Administrator")


class TestReturnForCorrection(WorkSummaryCase):
	def test_the_hod_can_hand_it_back(self):
		doc = self._send(self._summary())
		frappe.set_user(self.hod)
		ws.return_for_correction(doc.name, "Add the Kannur visits")
		frappe.set_user("Administrator")
		doc.reload()
		self.assertEqual(doc.custom_approval_status, ws.STATUS_RETURNED)
		self.assertEqual(doc.return_reason, "Add the Kannur visits")
		self.assertEqual(doc.current_approver, EMP_USER)
		self.assertEqual(doc.approval_flow, [])

	def test_the_employee_can_send_it_again(self):
		doc = self._send(self._summary())
		frappe.set_user(self.hod)
		ws.return_for_correction(doc.name, "not enough detail")
		frappe.set_user(EMP_USER)
		ws.send_for_remarks(doc.name)
		frappe.set_user("Administrator")
		doc.reload()
		self.assertEqual(doc.custom_approval_status, ws.STATUS_PENDING)
		self.assertEqual(doc.current_approver, self.hod)
		self.assertIsNone(doc.return_reason)

	def test_a_reason_is_required(self):
		doc = self._send(self._summary())
		frappe.set_user(self.hod)
		with self.assertRaises(frappe.ValidationError):
			ws.return_for_correction(doc.name, "")
		frappe.set_user("Administrator")


class TestGuards(WorkSummaryCase):
	def test_only_one_summary_per_employee_per_day(self):
		self._summary()
		frappe.set_user(EMP_USER)
		with self.assertRaises(frappe.ValidationError):
			self._summary()
		frappe.set_user("Administrator")

	def test_another_day_is_fine(self):
		self._summary()
		second = self._summary(work_date=add_days(today(), -1))
		self.assertTrue(second.name)

	def test_the_employee_cannot_write_the_hod_remark(self):
		doc = self._send(self._summary())
		frappe.set_user(EMP_USER)
		doc.reload()
		doc.hod_remarks = "I did great"
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)
		frappe.set_user("Administrator")

	def test_the_hod_cannot_write_the_gm_remark(self):
		doc = self._send(self._summary())
		frappe.set_user(self.hod)
		doc.reload()
		doc.gm_remarks = "Approved by me"
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)
		frappe.set_user("Administrator")

	def test_the_hod_may_write_the_hod_remark(self):
		doc = self._send(self._summary())
		frappe.set_user(self.hod)
		doc.reload()
		doc.hod_remarks = "Typed on the form"
		doc.save(ignore_permissions=True)
		frappe.set_user("Administrator")
		self.assertEqual(
			frappe.db.get_value("Daily Work Summary", doc.name, "hod_remarks"), "Typed on the form"
		)

	def test_somebody_outside_the_chain_cannot_act(self):
		doc = self._send(self._summary())
		frappe.set_user(OTHER_USER)
		with self.assertRaises(frappe.PermissionError):
			ws.add_remarks(doc.name, "not mine")
		with self.assertRaises(frappe.PermissionError):
			ws.return_for_correction(doc.name, "not mine")
		frappe.set_user("Administrator")

	def test_only_the_employee_may_send_their_own_summary(self):
		doc = self._summary()
		frappe.set_user(OTHER_USER)
		with self.assertRaises(frappe.PermissionError):
			ws.send_for_remarks(doc.name)
		frappe.set_user("Administrator")

	def test_sending_twice_is_refused(self):
		doc = self._send(self._summary())
		frappe.set_user(EMP_USER)
		with self.assertRaises(frappe.ValidationError):
			ws.send_for_remarks(doc.name)
		frappe.set_user("Administrator")

	def test_a_summary_with_no_tasks_cannot_be_sent(self):
		doc = self._summary()
		frappe.db.delete("Daily Work Summary Task", {"parent": doc.name})
		frappe.set_user(EMP_USER)
		with self.assertRaises(frappe.ValidationError):
			ws.send_for_remarks(doc.name)
		frappe.set_user("Administrator")

	def test_the_submit_button_cannot_skip_the_chain(self):
		doc = self._send(self._summary())
		frappe.set_user("Administrator")
		doc.reload()
		with self.assertRaises(frappe.ValidationError):
			doc.submit()


class TestVisibility(WorkSummaryCase):
	def test_the_hod_role_sees_it_waiting(self):
		doc = self._send(self._summary())
		frappe.set_user(self.hod)
		names = [r["name"] for r in ws.waiting_on_me()]
		frappe.set_user("Administrator")
		self.assertIn(doc.name, names)

	def test_the_gm_only_sees_it_once_it_reaches_them(self):
		doc = self._send(self._summary())
		frappe.set_user(self.gm)
		self.assertNotIn(doc.name, [r["name"] for r in ws.waiting_on_me()])
		frappe.set_user(self.hod)
		ws.add_remarks(doc.name, "passed on")
		frappe.set_user(self.gm)
		self.assertIn(doc.name, [r["name"] for r in ws.waiting_on_me()])
		frappe.set_user("Administrator")

	def test_an_unrelated_user_sees_nothing_waiting(self):
		self._send(self._summary())
		frappe.set_user(OTHER_USER)
		self.assertEqual(ws.waiting_on_me(), [])
		frappe.set_user("Administrator")

	def test_the_list_filter_keeps_other_people_out(self):
		doc = self._send(self._summary())
		frappe.set_user(OTHER_USER)
		condition = ws.get_permission_query_conditions()
		rows = frappe.db.sql(
			f"select name from `tabDaily Work Summary` where {condition}", pluck=True
		)
		frappe.set_user("Administrator")
		self.assertNotIn(doc.name, rows)

	def test_the_employee_and_the_hod_both_see_it(self):
		doc = self._send(self._summary())
		for user in (EMP_USER, self.hod):
			frappe.set_user(user)
			condition = ws.get_permission_query_conditions()
			rows = frappe.db.sql(
				f"select name from `tabDaily Work Summary` where {condition}", pluck=True
			)
			frappe.set_user("Administrator")
			self.assertIn(doc.name, rows, user)

	def test_has_permission_matches(self):
		doc = self._send(self._summary())
		self.assertTrue(ws.has_permission(doc, user=EMP_USER))
		self.assertTrue(ws.has_permission(doc, user=self.hod))
		self.assertFalse(ws.has_permission(doc, user=OTHER_USER))


class TestHodResolution(WorkSummaryCase):
	def test_sales_goes_to_the_sales_hod(self):
		self.assertEqual(ws.hod_role_for_department("Sales& Marketing - CA"), HOD_ROLE)
		self.assertEqual(ws.hod_role_for_department("Marketing - CA"), HOD_ROLE)

	def test_accounts_and_purchase_go_to_accounts(self):
		for dept in ("Accounts - CA", "Purchase - CA"):
			self.assertEqual(
				ws.hod_role_for_department(dept), "Accounts Manager Leave Approver", dept
			)

	def test_anything_else_goes_to_hr(self):
		for dept in (None, "", "Stores - CA"):
			self.assertEqual(ws.hod_role_for_department(dept), "HR Leave Approver")

	def test_the_chain_always_ends_at_the_gm(self):
		doc = self._summary()
		self.assertEqual(ws.chain_roles(doc)[-1], GM_ROLE)
