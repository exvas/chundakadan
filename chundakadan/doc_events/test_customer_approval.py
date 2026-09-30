import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.chundakadan.api import customer_approval as api
from chundakadan.doc_events.customer_approval import (
	ensure_customer_approval_fields,
	notify_approvers,
)

ROLE = "Customer Approval Test Role"
APPROVER = "customer.approver@example.com"
CREATOR = "customer.creator@example.com"


class CustomerApprovalCase(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		ensure_customer_approval_fields()
		self._sync_settings_doctype()
		self._make_role()
		self.approver = self._make_user(APPROVER, [ROLE, "Sales Master Manager"])
		self.creator = self._make_user(CREATOR, ["Sales Master Manager"])
		self.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
		self.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
		self.counter = 0

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.flags.in_import = False

	# -- fixtures ---------------------------------------------------------

	def _sync_settings_doctype(self):
		"""The dev copy has never migrated field_sales, so pull the Single in.
		This also proves the JSON edit that added the two fields is valid."""
		if frappe.get_meta(api.SETTINGS).has_field("enable_customer_approval"):
			return
		from frappe.modules.import_file import import_file_by_path

		import_file_by_path(
			frappe.get_app_path(
				"field_sales", "field_sales", "doctype",
				"chundakadan_settings", "chundakadan_settings.json",
			),
			force=True,
		)
		frappe.clear_cache(doctype=api.SETTINGS)

	def _make_role(self):
		if not frappe.db.exists("Role", ROLE):
			frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert()

	def _make_user(self, email, roles):
		if not frappe.db.exists("User", email):
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": email.split("@")[0],
				"send_welcome_email": 0, "user_type": "System User",
			}).insert()
		user = frappe.get_doc("User", email)
		user.add_roles(*roles)
		return email

	def _settings(self, enabled, role=ROLE):
		"""Set the two switches for this test."""
		frappe.db.set_single_value("Chundakadan Settings", {
			"enable_customer_approval": 1 if enabled else 0,
			"customer_approval_role": role or "",
		})

	def _new_customer(self, as_user=CREATOR, **extra):
		self.counter += 1
		name = extra.pop("customer_name", f"Approval test customer {frappe.generate_hash(length=6)}")
		frappe.set_user(as_user)
		doc = frappe.get_doc({
			"doctype": "Customer",
			"customer_name": name,
			"customer_group": self.customer_group,
			"territory": self.territory,
			"customer_type": "Company",
			**extra,
		})
		doc.insert(ignore_permissions=True)
		frappe.set_user("Administrator")
		return doc


class TestCustomerApprovalSwitch(CustomerApprovalCase):
	def test_off_by_default_leaves_the_customer_alone(self):
		self._settings(False)
		self.assertFalse(api.is_enabled())
		customer = self._new_customer()
		self.assertIn(customer.get(api.STATUS_FIELD), (None, ""))
		self.assertFalse(customer.disabled)

	def test_a_switch_with_no_role_is_still_off(self):
		self._settings(True, role="")
		self.assertFalse(api.is_enabled())
		customer = self._new_customer()
		self.assertFalse(customer.disabled)

	def test_on_needs_both_the_switch_and_the_role(self):
		self._settings(True)
		self.assertTrue(api.is_enabled())
		self.assertEqual(api.approval_role(), ROLE)


class TestHoldingNewItems(CustomerApprovalCase):
	def setUp(self):
		super().setUp()
		self._settings(True)

	def test_a_new_customer_is_pending_and_disabled(self):
		customer = self._new_customer()
		self.assertEqual(customer.get(api.STATUS_FIELD), api.PENDING)
		self.assertEqual(customer.disabled, 1)

	def test_the_approver_s_own_customer_is_approved_at_once(self):
		customer = self._new_customer(as_user=APPROVER)
		self.assertEqual(customer.get(api.STATUS_FIELD), api.APPROVED)
		self.assertFalse(customer.disabled)
		self.assertEqual(customer.custom_approved_by, APPROVER)
		self.assertTrue(customer.custom_approved_on)

	def test_an_import_skips_approval(self):
		frappe.flags.in_import = True
		try:
			customer = self._new_customer()
		finally:
			frappe.flags.in_import = False
		self.assertIn(customer.get(api.STATUS_FIELD), (None, ""))
		self.assertFalse(customer.disabled)

	def test_approver_users_are_the_role_holders(self):
		self.assertIn(APPROVER, api.approver_users())
		self.assertNotIn(CREATOR, api.approver_users())


class TestTheGuard(CustomerApprovalCase):
	def setUp(self):
		super().setUp()
		self._settings(True)
		self.customer = self._new_customer()

	def test_the_creator_cannot_approve_themselves(self):
		frappe.set_user(CREATOR)
		doc = frappe.get_doc("Customer", self.customer.name)
		doc.set(api.STATUS_FIELD, api.APPROVED)
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

	def test_the_creator_cannot_switch_disabled_off(self):
		frappe.set_user(CREATOR)
		doc = frappe.get_doc("Customer", self.customer.name)
		doc.disabled = 0
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

	def test_the_creator_cannot_write_the_approval_stamp(self):
		frappe.set_user(CREATOR)
		doc = frappe.get_doc("Customer", self.customer.name)
		doc.custom_approved_by = CREATOR
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

	def test_an_ordinary_edit_still_saves(self):
		frappe.set_user(CREATOR)
		doc = frappe.get_doc("Customer", self.customer.name)
		doc.customer_name = "Renamed while pending"
		doc.save(ignore_permissions=True)
		self.assertEqual(
			frappe.db.get_value("Customer", self.customer.name, "customer_name"), "Renamed while pending"
		)

	def test_the_approver_may_move_it(self):
		frappe.set_user(APPROVER)
		doc = frappe.get_doc("Customer", self.customer.name)
		doc.set(api.STATUS_FIELD, api.APPROVED)
		doc.disabled = 0
		doc.save(ignore_permissions=True)
		self.assertEqual(
			frappe.db.get_value("Customer", self.customer.name, api.STATUS_FIELD), api.APPROVED
		)


class TestApproveAndReject(CustomerApprovalCase):
	def setUp(self):
		super().setUp()
		self._settings(True)
		self.customer = self._new_customer()

	def test_approve_enables_the_item_and_stamps_it(self):
		frappe.set_user(APPROVER)
		result = api.approve(self.customer.name)
		self.assertEqual(result["approved"], [self.customer.name])
		row = frappe.db.get_value(
			"Customer", self.customer.name,
			[api.STATUS_FIELD, "disabled", "custom_approved_by", "custom_approved_on"],
			as_dict=True,
		)
		self.assertEqual(row.custom_approval_status, api.APPROVED)
		self.assertEqual(row.disabled, 0)
		self.assertEqual(row.custom_approved_by, APPROVER)
		self.assertTrue(row.custom_approved_on)

	def test_approve_applies_an_allowed_correction(self):
		frappe.set_user(APPROVER)
		api.approve(self.customer.name, {"customer_name": "Corrected name", "territory": self.territory})
		row = frappe.db.get_value(
			"Customer", self.customer.name, ["customer_name", "territory"], as_dict=True
		)
		self.assertEqual(row.customer_name, "Corrected name")
		self.assertEqual(row.territory, self.territory)

	def test_approve_refuses_a_field_outside_the_whitelist(self):
		frappe.set_user(APPROVER)
		with self.assertRaises(frappe.ValidationError):
			api.approve(self.customer.name, {"disabled": 0})
		self.assertEqual(
			frappe.db.get_value("Customer", self.customer.name, api.STATUS_FIELD), api.PENDING
		)

	def test_a_correction_needs_a_single_item(self):
		other = self._new_customer()
		frappe.set_user(APPROVER)
		with self.assertRaises(frappe.ValidationError):
			api.approve([self.customer.name, other.name], {"customer_name": "no"})

	def test_bulk_approve(self):
		second = self._new_customer()
		third = self._new_customer()
		frappe.set_user(APPROVER)
		result = api.approve([self.customer.name, second.name, third.name])
		self.assertEqual(len(result["approved"]), 3)
		for name in result["approved"]:
			self.assertEqual(frappe.db.get_value("Customer", name, "disabled"), 0)

	def test_reject_keeps_it_disabled_and_stores_the_reason(self):
		frappe.set_user(APPROVER)
		api.reject(self.customer.name, "Duplicate of 0209")
		row = frappe.db.get_value(
			"Customer", self.customer.name,
			[api.STATUS_FIELD, "disabled", "custom_rejection_reason"], as_dict=True,
		)
		self.assertEqual(row.custom_approval_status, api.REJECTED)
		self.assertEqual(row.disabled, 1)
		self.assertEqual(row.custom_rejection_reason, "Duplicate of 0209")

	def test_reject_without_a_reason_is_refused(self):
		frappe.set_user(APPROVER)
		for reason in ("", "   ", None):
			with self.assertRaises(frappe.ValidationError):
				api.reject(self.customer.name, reason)
		self.assertEqual(
			frappe.db.get_value("Customer", self.customer.name, api.STATUS_FIELD), api.PENDING
		)

	def test_an_item_cannot_be_approved_twice(self):
		frappe.set_user(APPROVER)
		api.approve(self.customer.name)
		with self.assertRaises(frappe.ValidationError):
			api.approve(self.customer.name)

	def test_a_rejected_item_cannot_then_be_approved(self):
		frappe.set_user(APPROVER)
		api.reject(self.customer.name, "wrong group")
		with self.assertRaises(frappe.ValidationError):
			api.approve(self.customer.name)

	def test_nothing_selected_is_refused(self):
		frappe.set_user(APPROVER)
		with self.assertRaises(frappe.ValidationError):
			api.approve([])
		with self.assertRaises(frappe.ValidationError):
			api.reject([], "reason")

	def test_only_the_role_may_approve(self):
		frappe.set_user(CREATOR)
		with self.assertRaises(frappe.PermissionError):
			api.approve(self.customer.name)
		with self.assertRaises(frappe.PermissionError):
			api.reject(self.customer.name, "no")
		with self.assertRaises(frappe.PermissionError):
			api.pending_customers()

	def test_the_actions_are_refused_while_the_feature_is_off(self):
		self._settings(False)
		frappe.set_user(APPROVER)
		with self.assertRaises(frappe.ValidationError):
			api.approve(self.customer.name)

	def test_a_json_list_from_the_client_is_accepted(self):
		second = self._new_customer()
		frappe.set_user(APPROVER)
		result = api.approve(f'["{self.customer.name}", "{second.name}"]')
		self.assertEqual(len(result["approved"]), 2)


class TestReading(CustomerApprovalCase):
	def setUp(self):
		super().setUp()
		self._settings(True)
		self.customer = self._new_customer(customer_name="Findable pending customer")

	def test_pending_items_lists_what_is_waiting(self):
		frappe.set_user(APPROVER)
		result = api.pending_customers()
		names = [r["name"] for r in result["customers"]]
		self.assertIn(self.customer.name, names)
		self.assertGreaterEqual(result["total"], 1)
		row = next(r for r in result["customers"] if r["name"] == self.customer.name)
		self.assertEqual(row["customer_group"], self.customer_group)
		self.assertEqual(row["territory"], self.territory)
		self.assertTrue(row["owner_name"])

	def test_an_approved_item_drops_off_the_list(self):
		frappe.set_user(APPROVER)
		api.approve(self.customer.name)
		names = [r["name"] for r in api.pending_customers()["customers"]]
		self.assertNotIn(self.customer.name, names)

	def test_search_narrows_the_list(self):
		frappe.set_user(APPROVER)
		names = [r["name"] for r in api.pending_customers(search="Findable")["customers"]]
		self.assertIn(self.customer.name, names)
		self.assertEqual(api.pending_customers(search="zzz-no-such-item")["customers"], [])

	def test_access_tells_the_mobile_app_who_may_approve(self):
		frappe.set_user(APPROVER)
		access = api.access()
		self.assertTrue(access["enabled"])
		self.assertTrue(access["can_approve"])
		self.assertEqual(access["role"], ROLE)
		self.assertGreaterEqual(access["pending_count"], 1)

		frappe.set_user(CREATOR)
		access = api.access()
		self.assertTrue(access["enabled"])
		self.assertFalse(access["can_approve"])
		self.assertEqual(access["pending_count"], 0)

	def test_access_while_the_feature_is_off(self):
		self._settings(False)
		frappe.set_user(APPROVER)
		access = api.access()
		self.assertFalse(access["enabled"])
		self.assertFalse(access["can_approve"])
		self.assertIsNone(access["role"])


class TestNotification(CustomerApprovalCase):
	def setUp(self):
		super().setUp()
		self._settings(True)

	def test_the_approvers_get_a_notification_log_row(self):
		customer = self._new_customer()
		notify_approvers(customer)
		logs = frappe.get_all(
			"Notification Log",
			filters={"for_user": APPROVER, "document_name": customer.name},
			fields=["subject", "document_type"],
		)
		self.assertTrue(logs, "no notification log row for the approver")
		self.assertEqual(logs[0].document_type, "Customer")
		self.assertNotIn(
			CREATOR,
			frappe.get_all("Notification Log", filters={"document_name": customer.name}, pluck="for_user"),
		)

	def test_an_approved_item_notifies_nobody(self):
		customer = self._new_customer(as_user=APPROVER)
		notify_approvers(customer)
		self.assertFalse(
			frappe.get_all("Notification Log", filters={"document_name": customer.name})
		)


class TestBackfillPatch(CustomerApprovalCase):
	def test_existing_customers_are_marked_approved_without_touching_disabled(self):
		from chundakadan.patches.mark_existing_customers_approved import execute

		ensure_customer_approval_fields()
		self._settings(False)
		open_customer = self._new_customer()
		frappe.db.set_value("Customer", open_customer.name, "custom_approval_status", None, update_modified=False)
		frappe.db.set_value("Customer", open_customer.name, "disabled", 1, update_modified=False)

		execute()

		row = frappe.db.get_value(
			"Customer", open_customer.name, ["custom_approval_status", "disabled"], as_dict=True
		)
		self.assertEqual(row.custom_approval_status, api.APPROVED)
		self.assertEqual(row.disabled, 1, "the patch must not re-enable anything")

	def test_the_patch_leaves_a_pending_customer_pending(self):
		from chundakadan.patches.mark_existing_customers_approved import execute

		ensure_customer_approval_fields()
		self._settings(True)
		pending = self._new_customer()
		execute()
		self.assertEqual(
			frappe.db.get_value("Customer", pending.name, "custom_approval_status"), api.PENDING
		)


class TestMobileEndpoints(CustomerApprovalCase):
	"""The field_sales wrappers must enforce exactly the same rules."""

	def setUp(self):
		super().setUp()
		self._settings(True)
		self.customer = self._new_customer()

	def _call(self, fn, **kwargs):
		frappe.local.response = frappe._dict()
		fn(**kwargs)
		return frappe.local.response

	def test_access_reports_the_tile_for_the_approver_only(self):
		from field_sales.Api.auth import customer_approval_access

		frappe.set_user(APPROVER)
		res = self._call(customer_approval_access)
		self.assertTrue(res["success"])
		self.assertTrue(res["data"]["can_approve"])

		frappe.set_user(CREATOR)
		res = self._call(customer_approval_access)
		self.assertFalse(res["data"]["can_approve"])

	def test_approve_from_the_app(self):
		from field_sales.Api.auth import approve_customers

		frappe.set_user(APPROVER)
		res = self._call(approve_customers, customers=[self.customer.name])
		self.assertTrue(res["success"])
		self.assertEqual(frappe.db.get_value("Customer", self.customer.name, "disabled"), 0)

	def test_approve_with_a_correction_from_the_app(self):
		from field_sales.Api.auth import approve_customers

		frappe.set_user(APPROVER)
		self._call(approve_customers, customers=[self.customer.name], changes={"customer_name": "Fixed on mobile"})
		self.assertEqual(
			frappe.db.get_value("Customer", self.customer.name, "customer_name"), "Fixed on mobile"
		)

	def test_reject_from_the_app(self):
		from field_sales.Api.auth import reject_customers

		frappe.set_user(APPROVER)
		res = self._call(reject_customers, customers=[self.customer.name], reason="Wrong brand")
		self.assertTrue(res["success"])
		self.assertEqual(
			frappe.db.get_value("Customer", self.customer.name, "custom_rejection_reason"), "Wrong brand"
		)

	def test_a_non_approver_is_refused_with_403(self):
		from field_sales.Api.auth import approve_customers, reject_customers

		frappe.set_user(CREATOR)
		res = self._call(approve_customers, customers=[self.customer.name])
		self.assertFalse(res["success"])
		self.assertEqual(res["http_status_code"], 403)

		res = self._call(reject_customers, customers=[self.customer.name], reason="no")
		self.assertEqual(res["http_status_code"], 403)
		self.assertEqual(
			frappe.db.get_value("Customer", self.customer.name, api.STATUS_FIELD), api.PENDING
		)

	def test_a_bad_request_comes_back_as_500_not_a_crash(self):
		from field_sales.Api.auth import reject_customers

		frappe.set_user(APPROVER)
		res = self._call(reject_customers, customers=[self.customer.name], reason="")
		self.assertFalse(res["success"])
		self.assertEqual(res["http_status_code"], 500)
