import frappe
from frappe.tests.utils import FrappeTestCase

from chundakadan.chundakadan.api import item_approval as api
from chundakadan.doc_events.item_approval import (
	ensure_item_approval_fields,
	notify_approvers,
)

ROLE = "Item Approval Test Role"
APPROVER = "item.approver@example.com"
CREATOR = "item.creator@example.com"


class ItemApprovalCase(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		ensure_item_approval_fields()
		self._sync_settings_doctype()
		self._make_role()
		self.approver = self._make_user(APPROVER, [ROLE, "Item Manager"])
		self.creator = self._make_user(CREATOR, ["Item Manager"])
		self.item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		self.hsn_code = frappe.db.get_value("GST HSN Code", {}, "name")
		self.brand = self._make_brand()
		self.counter = 0

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.flags.in_import = False

	# -- fixtures ---------------------------------------------------------

	def _sync_settings_doctype(self):
		"""The dev copy has never migrated field_sales, so pull the Single in.
		This also proves the JSON edit that added the two fields is valid."""
		if frappe.get_meta(api.SETTINGS).has_field("enable_item_approval"):
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

	def _make_brand(self):
		"""Brand is hash-named here but its `brand` column is unique, so look
		it up by the field and hand back the document name."""
		label = "Item Approval Test Brand"
		existing = frappe.db.get_value("Brand", {"brand": label}, "name")
		if existing:
			return existing
		return frappe.get_doc({"doctype": "Brand", "brand": label}).insert().name

	def _settings(self, enabled, role=ROLE):
		"""Set the two switches for this test."""
		frappe.db.set_single_value("Chundakadan Settings", {
			"enable_item_approval": 1 if enabled else 0,
			"item_approval_role": role or "",
		})

	def _new_item(self, as_user=CREATOR, **extra):
		self.counter += 1
		code = f"ITEM-APPR-{frappe.generate_hash(length=6)}-{self.counter}"
		frappe.set_user(as_user)
		doc = frappe.get_doc({
			"doctype": "Item",
			"item_code": code,
			"item_name": extra.pop("item_name", f"Approval test {self.counter}"),
			"item_group": self.item_group,
			"brand": self.brand,
			"stock_uom": "Nos",
			"gst_hsn_code": self.hsn_code,
			"is_stock_item": 0,
			**extra,
		})
		doc.insert(ignore_permissions=True)
		frappe.set_user("Administrator")
		return doc


class TestItemApprovalSwitch(ItemApprovalCase):
	def test_off_by_default_leaves_the_item_alone(self):
		self._settings(False)
		self.assertFalse(api.is_enabled())
		item = self._new_item()
		self.assertIn(item.get(api.STATUS_FIELD), (None, ""))
		self.assertFalse(item.disabled)

	def test_a_switch_with_no_role_is_still_off(self):
		self._settings(True, role="")
		self.assertFalse(api.is_enabled())
		item = self._new_item()
		self.assertFalse(item.disabled)

	def test_on_needs_both_the_switch_and_the_role(self):
		self._settings(True)
		self.assertTrue(api.is_enabled())
		self.assertEqual(api.approval_role(), ROLE)


class TestHoldingNewItems(ItemApprovalCase):
	def setUp(self):
		super().setUp()
		self._settings(True)

	def test_a_new_item_is_pending_and_disabled(self):
		item = self._new_item()
		self.assertEqual(item.get(api.STATUS_FIELD), api.PENDING)
		self.assertEqual(item.disabled, 1)

	def test_the_approver_s_own_item_is_approved_at_once(self):
		item = self._new_item(as_user=APPROVER)
		self.assertEqual(item.get(api.STATUS_FIELD), api.APPROVED)
		self.assertFalse(item.disabled)
		self.assertEqual(item.custom_approved_by, APPROVER)
		self.assertTrue(item.custom_approved_on)

	def test_an_import_skips_approval(self):
		frappe.flags.in_import = True
		try:
			item = self._new_item()
		finally:
			frappe.flags.in_import = False
		self.assertIn(item.get(api.STATUS_FIELD), (None, ""))
		self.assertFalse(item.disabled)

	def test_approver_users_are_the_role_holders(self):
		self.assertIn(APPROVER, api.approver_users())
		self.assertNotIn(CREATOR, api.approver_users())


class TestTheGuard(ItemApprovalCase):
	def setUp(self):
		super().setUp()
		self._settings(True)
		self.item = self._new_item()

	def test_the_creator_cannot_approve_themselves(self):
		frappe.set_user(CREATOR)
		doc = frappe.get_doc("Item", self.item.name)
		doc.set(api.STATUS_FIELD, api.APPROVED)
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

	def test_the_creator_cannot_switch_disabled_off(self):
		frappe.set_user(CREATOR)
		doc = frappe.get_doc("Item", self.item.name)
		doc.disabled = 0
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

	def test_the_creator_cannot_write_the_approval_stamp(self):
		frappe.set_user(CREATOR)
		doc = frappe.get_doc("Item", self.item.name)
		doc.custom_approved_by = CREATOR
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

	def test_an_ordinary_edit_still_saves(self):
		frappe.set_user(CREATOR)
		doc = frappe.get_doc("Item", self.item.name)
		doc.item_name = "Renamed while pending"
		doc.save(ignore_permissions=True)
		self.assertEqual(
			frappe.db.get_value("Item", self.item.name, "item_name"), "Renamed while pending"
		)

	def test_the_approver_may_move_it(self):
		frappe.set_user(APPROVER)
		doc = frappe.get_doc("Item", self.item.name)
		doc.set(api.STATUS_FIELD, api.APPROVED)
		doc.disabled = 0
		doc.save(ignore_permissions=True)
		self.assertEqual(
			frappe.db.get_value("Item", self.item.name, api.STATUS_FIELD), api.APPROVED
		)


class TestApproveAndReject(ItemApprovalCase):
	def setUp(self):
		super().setUp()
		self._settings(True)
		self.item = self._new_item()

	def test_approve_enables_the_item_and_stamps_it(self):
		frappe.set_user(APPROVER)
		result = api.approve(self.item.name)
		self.assertEqual(result["approved"], [self.item.name])
		row = frappe.db.get_value(
			"Item", self.item.name,
			[api.STATUS_FIELD, "disabled", "custom_approved_by", "custom_approved_on"],
			as_dict=True,
		)
		self.assertEqual(row.custom_approval_status, api.APPROVED)
		self.assertEqual(row.disabled, 0)
		self.assertEqual(row.custom_approved_by, APPROVER)
		self.assertTrue(row.custom_approved_on)

	def test_approve_applies_an_allowed_correction(self):
		frappe.set_user(APPROVER)
		api.approve(self.item.name, {"item_name": "Corrected name", "standard_rate": 250})
		row = frappe.db.get_value(
			"Item", self.item.name, ["item_name", "standard_rate"], as_dict=True
		)
		self.assertEqual(row.item_name, "Corrected name")
		self.assertEqual(row.standard_rate, 250)

	def test_approve_refuses_a_field_outside_the_whitelist(self):
		frappe.set_user(APPROVER)
		with self.assertRaises(frappe.ValidationError):
			api.approve(self.item.name, {"disabled": 0})
		self.assertEqual(
			frappe.db.get_value("Item", self.item.name, api.STATUS_FIELD), api.PENDING
		)

	def test_a_correction_needs_a_single_item(self):
		other = self._new_item()
		frappe.set_user(APPROVER)
		with self.assertRaises(frappe.ValidationError):
			api.approve([self.item.name, other.name], {"item_name": "no"})

	def test_bulk_approve(self):
		second = self._new_item()
		third = self._new_item()
		frappe.set_user(APPROVER)
		result = api.approve([self.item.name, second.name, third.name])
		self.assertEqual(len(result["approved"]), 3)
		for name in result["approved"]:
			self.assertEqual(frappe.db.get_value("Item", name, "disabled"), 0)

	def test_reject_keeps_it_disabled_and_stores_the_reason(self):
		frappe.set_user(APPROVER)
		api.reject(self.item.name, "Duplicate of 0209")
		row = frappe.db.get_value(
			"Item", self.item.name,
			[api.STATUS_FIELD, "disabled", "custom_rejection_reason"], as_dict=True,
		)
		self.assertEqual(row.custom_approval_status, api.REJECTED)
		self.assertEqual(row.disabled, 1)
		self.assertEqual(row.custom_rejection_reason, "Duplicate of 0209")

	def test_reject_without_a_reason_is_refused(self):
		frappe.set_user(APPROVER)
		for reason in ("", "   ", None):
			with self.assertRaises(frappe.ValidationError):
				api.reject(self.item.name, reason)
		self.assertEqual(
			frappe.db.get_value("Item", self.item.name, api.STATUS_FIELD), api.PENDING
		)

	def test_an_item_cannot_be_approved_twice(self):
		frappe.set_user(APPROVER)
		api.approve(self.item.name)
		with self.assertRaises(frappe.ValidationError):
			api.approve(self.item.name)

	def test_a_rejected_item_cannot_then_be_approved(self):
		frappe.set_user(APPROVER)
		api.reject(self.item.name, "wrong group")
		with self.assertRaises(frappe.ValidationError):
			api.approve(self.item.name)

	def test_nothing_selected_is_refused(self):
		frappe.set_user(APPROVER)
		with self.assertRaises(frappe.ValidationError):
			api.approve([])
		with self.assertRaises(frappe.ValidationError):
			api.reject([], "reason")

	def test_only_the_role_may_approve(self):
		frappe.set_user(CREATOR)
		with self.assertRaises(frappe.PermissionError):
			api.approve(self.item.name)
		with self.assertRaises(frappe.PermissionError):
			api.reject(self.item.name, "no")
		with self.assertRaises(frappe.PermissionError):
			api.pending_items()

	def test_the_actions_are_refused_while_the_feature_is_off(self):
		self._settings(False)
		frappe.set_user(APPROVER)
		with self.assertRaises(frappe.ValidationError):
			api.approve(self.item.name)

	def test_a_json_list_from_the_client_is_accepted(self):
		second = self._new_item()
		frappe.set_user(APPROVER)
		result = api.approve(f'["{self.item.name}", "{second.name}"]')
		self.assertEqual(len(result["approved"]), 2)


class TestReading(ItemApprovalCase):
	def setUp(self):
		super().setUp()
		self._settings(True)
		self.item = self._new_item(item_name="Findable pending item")

	def test_pending_items_lists_what_is_waiting(self):
		frappe.set_user(APPROVER)
		result = api.pending_items()
		names = [r["name"] for r in result["items"]]
		self.assertIn(self.item.name, names)
		self.assertGreaterEqual(result["total"], 1)
		row = next(r for r in result["items"] if r["name"] == self.item.name)
		self.assertEqual(row["item_group"], self.item_group)
		self.assertEqual(row["brand"], self.brand)
		self.assertTrue(row["owner_name"])

	def test_an_approved_item_drops_off_the_list(self):
		frappe.set_user(APPROVER)
		api.approve(self.item.name)
		names = [r["name"] for r in api.pending_items()["items"]]
		self.assertNotIn(self.item.name, names)

	def test_search_narrows_the_list(self):
		frappe.set_user(APPROVER)
		names = [r["name"] for r in api.pending_items(search="Findable")["items"]]
		self.assertIn(self.item.name, names)
		self.assertEqual(api.pending_items(search="zzz-no-such-item")["items"], [])

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


class TestNotification(ItemApprovalCase):
	def setUp(self):
		super().setUp()
		self._settings(True)

	def test_the_approvers_get_a_notification_log_row(self):
		item = self._new_item()
		notify_approvers(item)
		logs = frappe.get_all(
			"Notification Log",
			filters={"for_user": APPROVER, "document_name": item.name},
			fields=["subject", "document_type"],
		)
		self.assertTrue(logs, "no notification log row for the approver")
		self.assertEqual(logs[0].document_type, "Item")
		self.assertNotIn(
			CREATOR,
			frappe.get_all("Notification Log", filters={"document_name": item.name}, pluck="for_user"),
		)

	def test_an_approved_item_notifies_nobody(self):
		item = self._new_item(as_user=APPROVER)
		notify_approvers(item)
		self.assertFalse(
			frappe.get_all("Notification Log", filters={"document_name": item.name})
		)


class TestBackfillPatch(ItemApprovalCase):
	def test_existing_items_are_marked_approved_without_touching_disabled(self):
		from chundakadan.patches.mark_existing_items_approved import execute

		self._settings(False)
		open_item = self._new_item()
		frappe.db.set_value("Item", open_item.name, "custom_approval_status", None, update_modified=False)
		frappe.db.set_value("Item", open_item.name, "disabled", 1, update_modified=False)

		execute()

		row = frappe.db.get_value(
			"Item", open_item.name, ["custom_approval_status", "disabled"], as_dict=True
		)
		self.assertEqual(row.custom_approval_status, api.APPROVED)
		self.assertEqual(row.disabled, 1, "the patch must not re-enable anything")

	def test_the_patch_leaves_a_pending_item_pending(self):
		from chundakadan.patches.mark_existing_items_approved import execute

		self._settings(True)
		pending = self._new_item()
		execute()
		self.assertEqual(
			frappe.db.get_value("Item", pending.name, "custom_approval_status"), api.PENDING
		)


class TestMobileEndpoints(ItemApprovalCase):
	"""The field_sales wrappers must enforce exactly the same rules."""

	def setUp(self):
		super().setUp()
		self._settings(True)
		self.item = self._new_item()

	def _call(self, fn, **kwargs):
		frappe.local.response = frappe._dict()
		fn(**kwargs)
		return frappe.local.response

	def test_access_reports_the_tile_for_the_approver_only(self):
		from field_sales.Api.auth import item_approval_access

		frappe.set_user(APPROVER)
		res = self._call(item_approval_access)
		self.assertTrue(res["success"])
		self.assertTrue(res["data"]["can_approve"])

		frappe.set_user(CREATOR)
		res = self._call(item_approval_access)
		self.assertFalse(res["data"]["can_approve"])

	def test_approve_from_the_app(self):
		from field_sales.Api.auth import approve_items

		frappe.set_user(APPROVER)
		res = self._call(approve_items, items=[self.item.name])
		self.assertTrue(res["success"])
		self.assertEqual(frappe.db.get_value("Item", self.item.name, "disabled"), 0)

	def test_approve_with_a_correction_from_the_app(self):
		from field_sales.Api.auth import approve_items

		frappe.set_user(APPROVER)
		self._call(approve_items, items=[self.item.name], changes={"item_name": "Fixed on mobile"})
		self.assertEqual(
			frappe.db.get_value("Item", self.item.name, "item_name"), "Fixed on mobile"
		)

	def test_reject_from_the_app(self):
		from field_sales.Api.auth import reject_items

		frappe.set_user(APPROVER)
		res = self._call(reject_items, items=[self.item.name], reason="Wrong brand")
		self.assertTrue(res["success"])
		self.assertEqual(
			frappe.db.get_value("Item", self.item.name, "custom_rejection_reason"), "Wrong brand"
		)

	def test_a_non_approver_is_refused_with_403(self):
		from field_sales.Api.auth import approve_items, reject_items

		frappe.set_user(CREATOR)
		res = self._call(approve_items, items=[self.item.name])
		self.assertFalse(res["success"])
		self.assertEqual(res["http_status_code"], 403)

		res = self._call(reject_items, items=[self.item.name], reason="no")
		self.assertEqual(res["http_status_code"], 403)
		self.assertEqual(
			frappe.db.get_value("Item", self.item.name, api.STATUS_FIELD), api.PENDING
		)

	def test_a_bad_request_comes_back_as_500_not_a_crash(self):
		from field_sales.Api.auth import reject_items

		frappe.set_user(APPROVER)
		res = self._call(reject_items, items=[self.item.name], reason="")
		self.assertFalse(res["success"])
		self.assertEqual(res["http_status_code"], 500)
