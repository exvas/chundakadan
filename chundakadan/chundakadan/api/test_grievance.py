import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.chundakadan.api import grievance as gr

GM_ROLE = "GM Leave Approver"
RAISER = "grievance_raiser@chundakadan.test"
OTHER = "grievance_other@chundakadan.test"
GM = "grievance_gm@chundakadan.test"
HR = "grievance_hr@chundakadan.test"
HR_USER_ONLY = "grievance_hruser@chundakadan.test"


class GrievanceCase(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.company = frappe.db.get_value("Company", {}, "name")
		self.type = frappe.db.get_value("Grievance Type", {}, "name")
		if not (self.company and self.type):
			self.skipTest("no company or grievance type on this site")
		self.raiser = self._employee(RAISER, "Raiser")
		self.other = self._employee(OTHER, "Other")
		gr.ensure_grievance_permissions()
		frappe.clear_cache(doctype="Employee Grievance")
		self._user(GM, [GM_ROLE])
		self._user(HR, ["HR Manager"])
		self._user(HR_USER_ONLY, ["HR User"])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _user(self, email, roles):
		if not frappe.db.exists("User", email):
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": email.split("@")[0],
				"send_welcome_email": 0, "roles": [{"role": r} for r in roles],
			}).insert(ignore_permissions=True)
		else:
			doc = frappe.get_doc("User", email)
			doc.set("roles", [{"role": r} for r in roles])
			doc.save(ignore_permissions=True)
		return email

	def _employee(self, email, name):
		self._user(email, ["Employee"])
		existing = frappe.db.get_value("Employee", {"user_id": email}, "name")
		if existing:
			return existing
		return frappe.get_doc({
			"doctype": "Employee", "first_name": "Grievance " + name, "user_id": email,
			"company": self.company, "date_of_birth": "1995-01-01",
			"date_of_joining": "2026-01-01", "status": "Active",
			"gender": frappe.db.get_value("Gender", {}, "name"),
			"department": frappe.db.get_value("Department", {"is_group": 0}, "name"),
			"designation": frappe.db.get_value("Designation", {}, "name"),
			"holiday_list": frappe.db.get_value("Holiday List", {}, "name"),
		}).insert(ignore_permissions=True).name

	def _raise(self, as_user=RAISER, **values):
		frappe.set_user(as_user)
		try:
			return gr.raise_grievance(
				values.get("grievance_type", self.type),
				values.get("description", "The lift has been out for a week."),
			)
		finally:
			frappe.set_user("Administrator")

	def _visible_to(self, user):
		"""What this user's list view would show.

		get_list, never get_all: get_all ignores permissions, which would
		make every one of these checks pass whatever the rules say.
		"""
		frappe.set_user(user)
		try:
			return [r.name for r in frappe.get_list("Employee Grievance", fields=["name"])]
		finally:
			frappe.set_user("Administrator")


class TestRaisingOne(GrievanceCase):
	def test_the_type_and_the_description_are_enough(self):
		result = self._raise()
		doc = frappe.get_doc("Employee Grievance", result["name"])
		self.assertEqual(doc.grievance_type, self.type)
		self.assertEqual(doc.description, "The lift has been out for a week.")
		self.assertEqual(doc.raised_by, self.raiser)
		self.assertEqual(doc.status, "Open")

	def test_the_fields_hrms_insists_on_are_filled_in(self):
		"""The employee is not asked for a subject or a party."""
		doc = frappe.get_doc("Employee Grievance", self._raise()["name"])
		self.assertEqual(doc.subject, self.type)
		self.assertEqual(doc.grievance_against_party, "Company")
		self.assertEqual(doc.grievance_against, self.company)

	def test_a_description_is_required(self):
		with self.assertRaises(frappe.ValidationError):
			self._raise(description="   ")

	def test_a_type_is_required(self):
		with self.assertRaises(frappe.ValidationError):
			self._raise(grievance_type="")

	def test_an_unknown_type_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self._raise(grievance_type="Not A Real Type")

	def test_somebody_with_no_employee_record_cannot_raise_one(self):
		self._user("grievance_nobody@chundakadan.test", ["Employee"])
		frappe.set_user("grievance_nobody@chundakadan.test")
		try:
			with self.assertRaises(frappe.ValidationError):
				gr.raise_grievance(self.type, "something")
		finally:
			frappe.set_user("Administrator")

	def test_the_types_come_from_the_predefined_list(self):
		types = gr.grievance_types()
		self.assertIn(self.type, types)
		self.assertEqual(types, sorted(types))


class TestWhoCanRead(GrievanceCase):
	def setUp(self):
		super().setUp()
		self.mine = self._raise()["name"]

	def test_the_gm_reads_every_grievance(self):
		self.assertIn(self.mine, self._visible_to(GM))

	def test_the_hr_manager_reads_every_grievance(self):
		self.assertIn(self.mine, self._visible_to(HR))

	def test_an_hr_user_reads_none(self):
		"""Fourteen people hold HR User, most of them ordinary staff."""
		self.assertNotIn(self.mine, self._visible_to(HR_USER_ONLY))

	def test_another_employee_reads_none(self):
		self.assertNotIn(self.mine, self._visible_to(OTHER))

	def test_the_person_who_raised_it_reads_their_own(self):
		self.assertIn(self.mine, self._visible_to(RAISER))

	def test_has_permission_agrees_with_the_list(self):
		doc = frappe.get_doc("Employee Grievance", self.mine)
		self.assertTrue(gr.has_permission(doc, user=GM))
		self.assertTrue(gr.has_permission(doc, user=HR))
		self.assertTrue(gr.has_permission(doc, user=RAISER))
		self.assertFalse(gr.has_permission(doc, user=OTHER))
		self.assertFalse(gr.has_permission(doc, user=HR_USER_ONLY))

	def test_my_grievances_lists_only_the_callers_own(self):
		frappe.set_user(OTHER)
		try:
			gr.raise_grievance(self.type, "A different complaint.")
		finally:
			frappe.set_user("Administrator")
		frappe.set_user(RAISER)
		try:
			mine = gr.my_grievances()
		finally:
			frappe.set_user("Administrator")
		self.assertEqual([row["name"] for row in mine], [self.mine])

	def test_the_query_condition_shuts_out_a_user_with_no_employee(self):
		self._user("grievance_nobody2@chundakadan.test", ["Employee"])
		self.assertEqual(
			gr.get_permission_query_conditions("grievance_nobody2@chundakadan.test"), "1 = 0"
		)

	def test_the_query_condition_is_empty_for_the_gm(self):
		self.assertEqual(gr.get_permission_query_conditions(GM), "")

	def test_the_gm_role_carries_the_permission_on_its_own(self):
		"""Not borrowed from HR Manager, which the GM may lose one day."""
		gr.ensure_grievance_permissions()
		self.assertTrue(frappe.db.exists(
			"Custom DocPerm", {"parent": "Employee Grievance", "role": GM_ROLE, "read": 1}
		))

	def test_granting_it_twice_adds_one_row(self):
		gr.ensure_grievance_permissions()
		gr.ensure_grievance_permissions()
		self.assertEqual(frappe.db.count(
			"Custom DocPerm", {"parent": "Employee Grievance", "role": GM_ROLE}
		), 1)
