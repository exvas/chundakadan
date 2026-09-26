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


class TestWhoSeesEverything(WorkSummaryCase):
	"""The GM closes every chain, so a draft nobody sent is still theirs to
	see -- but seeing is not acting."""

	def _visible_to(self, user):
		frappe.set_user(user)
		try:
			condition = ws.get_permission_query_conditions()
			if not condition:
				return frappe.get_all("Daily Work Summary", pluck="name", ignore_permissions=True)
			return frappe.db.sql(
				f"select name from `tabDaily Work Summary` where {condition}", pluck=True
			)
		finally:
			frappe.set_user("Administrator")

	def test_the_gm_sees_a_draft_that_was_never_sent(self):
		draft = self._summary()
		self.assertEqual(draft.custom_approval_status, ws.STATUS_DRAFT)
		self.assertEqual(draft.approval_flow, [])
		self.assertIn(draft.name, self._visible_to(self.gm))
		self.assertTrue(ws.has_permission(draft, user=self.gm))

	def test_the_hod_does_not_see_a_draft_that_was_never_sent(self):
		draft = self._summary()
		self.assertNotIn(draft.name, self._visible_to(self.hod))

	def test_the_hod_sees_it_once_it_is_sent(self):
		sent = self._send(self._summary())
		self.assertIn(sent.name, self._visible_to(self.hod))

	def test_an_unrelated_employee_still_sees_nothing(self):
		draft = self._summary()
		self.assertNotIn(draft.name, self._visible_to(OTHER_USER))
		self.assertFalse(ws.has_permission(draft, user=OTHER_USER))

	def test_seeing_everything_is_not_acting_on_everything(self):
		"""The GM may open a summary sitting with the HOD, but not sign it."""
		sent = self._send(self._summary())
		self.assertIn(sent.name, self._visible_to(self.gm))
		self.assertTrue(ws.sees_everything(self.gm))
		self.assertFalse(ws.can_act_now(sent, self.gm))
		frappe.set_user(self.gm)
		try:
			with self.assertRaises(frappe.PermissionError):
				ws.add_remarks(sent.name, "signing out of turn")
		finally:
			frappe.set_user("Administrator")

	def test_the_gm_still_only_gets_their_own_step_in_waiting_on_me(self):
		sent = self._send(self._summary())
		frappe.set_user(self.gm)
		waiting = [r["name"] for r in ws.waiting_on_me()]
		frappe.set_user("Administrator")
		self.assertNotIn(sent.name, waiting, "it is still with the HOD")


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


class TestRemindersAndStatus(WorkSummaryCase):
	"""Phase 3 — who has not sent today's summary."""

	def _settings(self, enabled, time_value="18:00:00"):
		frappe.db.set_single_value("Chundakadan Settings", {
			"enable_work_summary_reminder": 1 if enabled else 0,
			"work_summary_reminder_time": time_value,
		})

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.get_meta("Chundakadan Settings").has_field("enable_work_summary_reminder"):
			import_file_by_path(
				frappe.get_app_path(
					"field_sales", "field_sales", "doctype",
					"chundakadan_settings", "chundakadan_settings.json",
				),
				force=True,
			)
			frappe.clear_cache(doctype="Chundakadan Settings")

	def test_an_employee_with_no_summary_is_listed(self):
		missing = [e.name for e in ws.not_submitted(today())]
		self.assertIn(self.employee, missing)

	def test_a_draft_still_counts_as_not_submitted(self):
		self._summary()
		missing = [e.name for e in ws.not_submitted(today())]
		self.assertIn(self.employee, missing, "a draft nobody sent is still missing")

	def test_sending_takes_them_off_the_list(self):
		self._send(self._summary())
		missing = [e.name for e in ws.not_submitted(today())]
		self.assertNotIn(self.employee, missing)

	def test_a_returned_summary_counts_as_not_submitted_again(self):
		doc = self._send(self._summary())
		frappe.set_user(self.hod)
		ws.return_for_correction(doc.name, "redo it")
		frappe.set_user("Administrator")
		self.assertIn(self.employee, [e.name for e in ws.not_submitted(today())])

	def test_a_holiday_is_not_a_missing_summary(self):
		holiday_list = frappe.db.get_value("Employee", self.employee, "holiday_list") or \
			frappe.db.get_value("Company", self.company, "default_holiday_list")
		if not holiday_list:
			self.skipTest("no holiday list on this site")
		day = add_days(today(), -400)
		# other tests commit, so a row left by an earlier run survives
		frappe.db.delete("Holiday", {"parent": holiday_list, "holiday_date": day})
		frappe.get_doc("Holiday List", holiday_list).append(
			"holidays", {"holiday_date": day, "description": "DWS test holiday"}
		).db_insert()
		self.assertNotIn(self.employee, [e.name for e in ws.not_submitted(day)])

	def test_approved_leave_is_not_a_missing_summary(self):
		day = add_days(today(), -401)
		frappe.db.delete("Leave Application", {"employee": self.employee, "from_date": day})
		self.assertIn(self.employee, [e.name for e in ws.not_submitted(day)])
		leave_type = frappe.db.get_value("Leave Type", {}, "name")
		if not leave_type:
			self.skipTest("no leave type on this site")
		frappe.get_doc({
			"doctype": "Leave Application", "employee": self.employee,
			"leave_type": leave_type, "from_date": day, "to_date": day,
			"company": self.company, "status": "Approved", "docstatus": 1,
			"posting_date": day,
		}).db_insert()
		self.assertNotIn(self.employee, [e.name for e in ws.not_submitted(day)])

	def test_the_department_filter_narrows_it(self):
		department = frappe.db.get_value("Employee", self.employee, "department")
		names = [e.name for e in ws.not_submitted(today(), department=department)]
		self.assertIn(self.employee, names)
		other = frappe.db.get_value("Department", {"name": ["!=", department]}, "name")
		if other:
			self.assertNotIn(self.employee, [e.name for e in ws.not_submitted(today(), department=other)])

	def test_the_reminder_stays_quiet_while_it_is_switched_off(self):
		self._settings(False)
		self.assertIsNone(ws.send_submission_reminders())

	def test_the_reminder_only_fires_in_its_own_hour(self):
		from frappe.utils import now_datetime

		this_hour = now_datetime().hour
		other_hour = (this_hour + 1) % 24
		self._settings(True, f"{other_hour:02d}:00:00")
		before = frappe.db.count("Notification Log")
		ws.send_submission_reminders()
		self.assertEqual(frappe.db.count("Notification Log"), before)

	def test_the_reminder_reaches_whoever_has_not_sent(self):
		from frappe.utils import now_datetime

		self._settings(True, f"{now_datetime().hour:02d}:00:00")
		ws.send_submission_reminders()
		logs = frappe.get_all(
			"Notification Log", filters={"for_user": EMP_USER}, pluck="subject"
		)
		self.assertTrue(any("work summary" in (s or "").lower() for s in logs), logs)

	def test_the_reminder_skips_whoever_already_sent(self):
		from frappe.utils import now_datetime

		self._send(self._summary())
		frappe.db.delete("Notification Log", {"for_user": EMP_USER})
		self._settings(True, f"{now_datetime().hour:02d}:00:00")
		ws.send_submission_reminders()
		self.assertFalse(frappe.get_all("Notification Log", filters={"for_user": EMP_USER}))


class TestStatusReport(WorkSummaryCase):
	def _run(self, **extra):
		from chundakadan.chundakadan.report.daily_work_summary_status.daily_work_summary_status import execute

		filters = {"from_date": today(), "to_date": today(), "employee": self.employee}
		filters.update(extra)
		return execute(filters)

	def test_columns(self):
		columns, _data = self._run()
		names = [c["fieldname"] for c in columns]
		for field in ("work_date", "employee", "status", "summary", "task_count"):
			self.assertIn(field, names)

	def test_a_missing_day_reads_not_submitted(self):
		_columns, data = self._run()
		self.assertEqual(len(data), 1)
		self.assertEqual(data[0]["status"], "Not Submitted")
		self.assertIsNone(data[0]["summary"])

	def test_a_sent_summary_shows_its_status_and_task_count(self):
		doc = self._send(self._summary())
		_columns, data = self._run()
		self.assertEqual(data[0]["summary"], doc.name)
		self.assertEqual(data[0]["status"], ws.STATUS_PENDING)
		self.assertEqual(data[0]["task_count"], 2)
		self.assertEqual(data[0]["current_approver"], self.hod)

	def test_only_missing_hides_the_ones_that_went_out(self):
		self._send(self._summary())
		_columns, data = self._run(only_missing=1)
		self.assertEqual(data, [])

	def test_a_range_gives_a_row_per_day(self):
		_columns, data = self._run(from_date=add_days(today(), -2))
		self.assertEqual(len(data), 3)

	def test_a_reversed_or_huge_range_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self._run(from_date=today(), to_date=add_days(today(), -1))
		with self.assertRaises(frappe.ValidationError):
			self._run(from_date=add_days(today(), -400))


class TestMobileEndpoints(WorkSummaryCase):
	def _call(self, fn, **kwargs):
		frappe.local.response = frappe._dict()
		fn(**kwargs)
		return frappe.local.response

	def _with_args(self, args):
		frappe.local.request = frappe._dict(args=frappe._dict(args))

	def test_saving_creates_the_day_s_summary(self):
		from field_sales.Api.auth import save_work_summary

		frappe.set_user(EMP_USER)
		res = self._call(save_work_summary, tasks=[{"task": "Visit", "work_description": "3 shops"}])
		frappe.set_user("Administrator")
		self.assertTrue(res["success"], res)
		self.assertEqual(res["data"]["custom_approval_status"], ws.STATUS_DRAFT)
		self.assertEqual(len(res["data"]["tasks"]), 1)

	def test_saving_again_the_same_day_updates_it(self):
		from field_sales.Api.auth import save_work_summary

		frappe.set_user(EMP_USER)
		first = self._call(save_work_summary, tasks=[{"task": "Visit", "work_description": "3 shops"}])
		second = self._call(save_work_summary, tasks=[
			{"task": "Visit", "work_description": "3 shops"},
			{"task": "Collection", "work_description": "2 cheques"},
		])
		frappe.set_user("Administrator")
		self.assertEqual(first["data"]["name"], second["data"]["name"])
		self.assertEqual(len(second["data"]["tasks"]), 2)

	def test_saving_with_send_puts_it_in_front_of_the_hod(self):
		from field_sales.Api.auth import save_work_summary

		frappe.set_user(EMP_USER)
		res = self._call(save_work_summary, tasks=[{"task": "Visit", "work_description": "3 shops"}], send=1)
		frappe.set_user("Administrator")
		name = res["data"]["name"]
		self.assertEqual(
			frappe.db.get_value("Daily Work Summary", name, "custom_approval_status"), ws.STATUS_PENDING
		)

	def test_a_summary_with_no_tasks_is_refused(self):
		from field_sales.Api.auth import save_work_summary

		frappe.set_user(EMP_USER)
		res = self._call(save_work_summary, tasks=[{"task": "   ", "work_description": "x"}])
		frappe.set_user("Administrator")
		self.assertFalse(res["success"])

	def test_a_sent_summary_cannot_be_edited_from_the_app(self):
		from field_sales.Api.auth import save_work_summary

		self._send(self._summary())
		frappe.set_user(EMP_USER)
		res = self._call(save_work_summary, tasks=[{"task": "Sneaky", "work_description": "edit"}])
		frappe.set_user("Administrator")
		self.assertEqual(res["http_status_code"], 403)

	def test_my_summaries_lists_the_caller_s_own(self):
		from field_sales.Api.auth import get_my_work_summaries

		doc = self._summary()
		self._with_args({})
		frappe.set_user(EMP_USER)
		res = self._call(get_my_work_summaries)
		frappe.set_user("Administrator")
		self.assertIn(doc.name, [s["name"] for s in res["data"]["summaries"]])

	def test_the_team_list_is_what_is_waiting_on_the_approver(self):
		from field_sales.Api.auth import get_team_work_summaries

		doc = self._send(self._summary())
		frappe.set_user(self.hod)
		res = self._call(get_team_work_summaries)
		frappe.set_user("Administrator")
		names = [s["name"] for s in res["data"]["summaries"]]
		self.assertIn(doc.name, names)
		self.assertEqual(res["data"]["summaries"][0]["tasks"][0]["task"], "Customer visit")

	def test_the_team_list_is_empty_for_everybody_else(self):
		from field_sales.Api.auth import get_team_work_summaries

		self._send(self._summary())
		frappe.set_user(OTHER_USER)
		res = self._call(get_team_work_summaries)
		frappe.set_user("Administrator")
		self.assertEqual(res["data"]["summaries"], [])

	def test_remarks_from_the_app_move_it_along(self):
		from field_sales.Api.auth import work_summary_add_remarks

		doc = self._send(self._summary())
		frappe.set_user(self.hod)
		res = self._call(work_summary_add_remarks, docname=doc.name, remarks="Seen")
		frappe.set_user("Administrator")
		self.assertEqual(res["data"]["status"], ws.STATUS_PARTIAL)
		self.assertEqual(frappe.db.get_value("Daily Work Summary", doc.name, "hod_remarks"), "Seen")

	def test_returning_from_the_app(self):
		from field_sales.Api.auth import work_summary_return

		doc = self._send(self._summary())
		frappe.set_user(self.hod)
		res = self._call(work_summary_return, docname=doc.name, reason="Add Kannur")
		frappe.set_user("Administrator")
		self.assertEqual(res["data"]["status"], ws.STATUS_RETURNED)

	def test_an_outsider_is_refused_with_403(self):
		from field_sales.Api.auth import work_summary_add_remarks, work_summary_return

		doc = self._send(self._summary())
		frappe.set_user(OTHER_USER)
		self.assertEqual(self._call(work_summary_add_remarks, docname=doc.name, remarks="x")["http_status_code"], 403)
		self.assertEqual(self._call(work_summary_return, docname=doc.name, reason="x")["http_status_code"], 403)
		frappe.set_user("Administrator")

	def test_access_tells_the_app_what_to_show(self):
		from field_sales.Api.auth import work_summary_access

		self._send(self._summary())
		frappe.set_user(EMP_USER)
		mine = self._call(work_summary_access)["data"]
		frappe.set_user(self.hod)
		theirs = self._call(work_summary_access)["data"]
		frappe.set_user("Administrator")
		self.assertTrue(mine["can_submit"])
		self.assertFalse(mine["is_approver"])
		self.assertTrue(theirs["is_approver"])
		self.assertGreaterEqual(theirs["pending_count"], 1)


class TestPermissions(WorkSummaryCase):
	"""Everybody writes their own summary, so every role on the doctype can
	create one -- an approver is an employee too."""

	def setUp(self):
		super().setUp()
		_import("daily_work_summary.json")

	def test_every_role_on_the_doctype_can_create(self):
		perms = frappe.get_all(
			"DocPerm", filters={"parent": "Daily Work Summary"},
			fields=["role", "create", "read", "write"],
		)
		self.assertTrue(perms)
		for perm in perms:
			self.assertEqual(perm.create, 1, perm.role)
			self.assertEqual(perm.read, 1, perm.role)
			self.assertEqual(perm.write, 1, perm.role)

	def test_the_employee_role_is_among_them(self):
		roles = {p.role for p in frappe.get_all(
			"DocPerm", filters={"parent": "Daily Work Summary"}, fields=["role"]
		)}
		self.assertIn("Employee", roles)

	def test_an_approver_can_create_their_own_summary(self):
		approver_employee = frappe.db.get_value("Employee", {"user_id": self.hod}, "name")
		if not approver_employee:
			self.skipTest("the resolved HOD has no employee record")
		frappe.set_user(self.hod)
		try:
			self.assertTrue(frappe.has_permission("Daily Work Summary", "create"))
		finally:
			frappe.set_user("Administrator")
