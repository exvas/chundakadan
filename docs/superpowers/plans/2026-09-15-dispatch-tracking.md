# Dispatch Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a Dispatch User track every Chundakadan Agencies Sales Invoice from Pending through Dispatched to Delivered from a desk page, with transport details synced to the invoice and e-Waybill.

**Architecture:** A `Dispatch Log` DocType (one per invoice) holds status, transport and delivery data; Sales Invoice hooks create logs; a `chundakadan.dispatch` package holds setup, events, sync and the whitelisted API; a standard desk Page renders tabs and dialogs over that API.

**Tech Stack:** Frappe/ERPNext v15, India Compliance e-Waybill utils, FrappeTestCase, vanilla Frappe desk JS.

**Spec:** `docs/superpowers/specs/2026-09-15-dispatch-tracking-design.md`

## Global Constraints

- Company in scope: `Chundakadan Agencies` only; submitted, `is_return = 0`, `is_opening != "Yes"`.
- Backfill from `2026-09-13`.
- Role name `Dispatch User`; page name `dispatch`; DocType `Dispatch Log`, naming `DSP-.YY.-.#####`.
- Invoice submit must never be blocked by dispatch code.
- Production is Frappe Cloud: all changes ship as app code via `git push upstream main`; the old server site `erp.chundakadan.in` (bench frappe-bench-15-india) is a stale copy used only for tests.
- Tests must never call the live e-Waybill portal: patch `india_compliance.gst_india.utils.e_waybill.update_transporter` / `update_vehicle_info` whenever the invoice has an `ewaybill`.
- Tests run with `bench --site erp.chundakadan.in run-tests --skip-test-records --module <module>`; FrappeTestCase rolls back at class end.

---

### Task 1: Setup module (role, Sales Invoice field, permissions) and constants

**Files:**
- Create/Modify: `chundakadan/dispatch/__init__.py`
- Create/Modify: `chundakadan/dispatch/constants.py`
- Create/Modify: `chundakadan/dispatch/setup.py`
- Create/Modify: `edit_hooks.py (applies hooks.py + patches.txt edits)`


**Interfaces:**
- Produces: `chundakadan.dispatch.constants` (COMPANY, BACKFILL_FROM, ROLE, PENDING, DISPATCHED, PICKUP, DELIVERED, NOT_DELIVERED, PENDING_REASONS, EXPECTED_DAYS, TRANSPORT_FIELDS)
- Produces: `setup.ensure_dispatch_role()`, `setup.ensure_sales_invoice_field()`, `setup.ensure_dispatch_permissions()`, `setup.ensure_dispatch_setup()` (commits; hook only)
- Hooks: before_migrate `ensure_dispatch_role`; after_migrate `ensure_dispatch_setup`; Sales Invoice on_submit `chundakadan.dispatch.events.create_dispatch_log`, on_cancel `chundakadan.dispatch.events.mark_invoice_cancelled`; patches.txt `chundakadan.patches.backfill_dispatch_logs`

- [ ] **Step 1: Create the constants and setup modules**

````python
# file: chundakadan/dispatch/__init__.py

````

````python
# file: chundakadan/dispatch/constants.py
"""Shared values for dispatch tracking (spec: 2026-09-15-dispatch-tracking-design)."""

COMPANY = "Chundakadan Agencies"
BACKFILL_FROM = "2026-09-13"
ROLE = "Dispatch User"

PENDING = "Pending"
DISPATCHED = "Dispatched"
PICKUP = "Customer Pickup"
DELIVERED = "Delivered"
NOT_DELIVERED = "Not Delivered"

PENDING_REASONS = (
	"Stock Not Available",
	"Payment Pending",
	"Customer Asked to Hold",
	"Transport Not Available",
	"Other",
)

# expected_delivery option -> calendar days after the dispatch date
EXPECTED_DAYS = {
	"Next Day": 1,
	"2 Days": 2,
	"After 2 Days": 3,
}

# Transport fields shared by Dispatch Log and Sales Invoice
TRANSPORT_FIELDS = (
	"transporter",
	"transporter_name",
	"gst_transporter_id",
	"vehicle_no",
	"lr_no",
	"lr_date",
	"driver_name",
	"mode_of_transport",
)
````

````python
# file: chundakadan/dispatch/setup.py
"""Site setup for dispatch tracking: role, Sales Invoice field, permissions.

ensure_dispatch_role runs in before_migrate so the role exists before the
Dispatch Log DocType and Dispatch page (which reference it) are synced.
ensure_dispatch_setup runs in after_migrate. Both are idempotent.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission

from chundakadan.dispatch import constants as C

# Doctypes a Dispatch User must be able to read from the Dispatch page:
# open the invoice, pick a transporter, see the customer.
DISPATCH_READ_DOCTYPES = ("Sales Invoice", "Supplier", "Customer")


def ensure_dispatch_role(*args, **kwargs):
	if frappe.db.exists("Role", C.ROLE):
		return
	frappe.get_doc({"doctype": "Role", "role_name": C.ROLE, "desk_access": 1}).insert(
		ignore_permissions=True
	)


def ensure_sales_invoice_field():
	create_custom_fields(
		{
			"Sales Invoice": [
				{
					"fieldname": "dispatch_status",
					"label": "Dispatch Status",
					"fieldtype": "Data",
					"insert_after": "transporter_info",
					"read_only": 1,
					"allow_on_submit": 1,
					"no_copy": 1,
					"in_list_view": 1,
					"in_standard_filter": 1,
					"module": "Chundakadan",
				}
			]
		},
		update=True,
	)


def ensure_dispatch_permissions():
	# add_permission copies the standard DocPerms into Custom DocPerm first,
	# so existing roles keep their access.
	for doctype in DISPATCH_READ_DOCTYPES:
		if frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": C.ROLE, "permlevel": 0}):
			continue
		add_permission(doctype, C.ROLE, 0)
		frappe.clear_cache(doctype=doctype)


def ensure_dispatch_setup(*args, **kwargs):
	ensure_dispatch_role()
	ensure_sales_invoice_field()
	ensure_dispatch_permissions()
	frappe.db.commit()
````

- [ ] **Step 2: Apply hooks.py and patches.txt edits (idempotent script; aborts if an anchor is missing)**

````python
# file: edit_hooks.py
"""Edit hooks.py and patches.txt for dispatch tracking. Idempotent; aborts on missing anchors."""
import sys

APP = "/home/frappe/frappe-bench-15-india/apps/chundakadan/chundakadan"

hk = APP + "/hooks.py"
h = open(hk).read()

if "chundakadan.dispatch.events.create_dispatch_log" not in h:
    anchor = '        "on_trash": "chundakadan.doc_events.sales_invoice.on_trash",'
    if h.count(anchor) != 1:
        sys.exit("hooks.py: Sales Invoice on_trash anchor not found once")
    h = h.replace(
        anchor,
        anchor
        + '\n        "on_submit": "chundakadan.dispatch.events.create_dispatch_log",'
        + '\n        "on_cancel": "chundakadan.dispatch.events.mark_invoice_cancelled",',
    )
    print("hooks.py: Sales Invoice on_submit/on_cancel added")

if "chundakadan.dispatch.setup.ensure_dispatch_role" not in h:
    anchor = 'before_migrate = [\n'
    if h.count(anchor) != 1:
        sys.exit("hooks.py: before_migrate anchor not found once")
    h = h.replace(anchor, anchor + '    "chundakadan.dispatch.setup.ensure_dispatch_role",\n')
    print("hooks.py: before_migrate ensure_dispatch_role added")

if "chundakadan.dispatch.setup.ensure_dispatch_setup" not in h:
    anchor = '    "chundakadan.install.ensure_sick_leave_deduction_component",\n]\n\n# Uninstallation'
    if h.count(anchor) != 1:
        sys.exit("hooks.py: after_migrate closing anchor not found once")
    h = h.replace(
        anchor,
        '    "chundakadan.install.ensure_sick_leave_deduction_component",\n'
        '    "chundakadan.dispatch.setup.ensure_dispatch_setup",\n]\n\n# Uninstallation',
    )
    print("hooks.py: after_migrate ensure_dispatch_setup added")

open(hk, "w").write(h)

pt = APP + "/patches.txt"
p = open(pt).read()
entry = "chundakadan.patches.backfill_dispatch_logs"
if entry not in p:
    open(pt, "w").write(p.rstrip("\n") + "\n" + entry + "\n")
    print("patches.txt: backfill_dispatch_logs added")
````

- [ ] **Step 3: Verify**

Run on the server: `./env/bin/python /tmp/imp/edit_hooks.py`, then `python -c 'import ast; ast.parse(open("apps/chundakadan/chundakadan/hooks.py").read())'`. Expected: edits printed, syntax OK. Then create the role on the test site: `bench --site erp.chundakadan.in execute chundakadan.dispatch.setup.ensure_dispatch_role`.

- [ ] **Step 4: Commit**

```bash
git add -A chundakadan && git commit -m "feat(dispatch): setup module, role, hooks"
```

### Task 2: Dispatch Log DocType with status rules

**Files:**
- Create/Modify: `chundakadan/chundakadan/doctype/dispatch_log/__init__.py`
- Create/Modify: `chundakadan/chundakadan/doctype/dispatch_log/dispatch_log.json`
- Create/Modify: `chundakadan/chundakadan/doctype/dispatch_log/dispatch_log.py`
- Create/Modify: `chundakadan/chundakadan/doctype/dispatch_log/test_dispatch_log.py`


**Interfaces:**
- Consumes: constants, `setup.ensure_dispatch_role`, `setup.ensure_sales_invoice_field` (Task 1); `events.build_log` (Task 3, imported lazily inside test helpers)
- Produces: DocType `Dispatch Log`; `DispatchLog.validate` (transition rules, dispatch stamps, expected date), `DispatchLog.on_update` (mirror `dispatch_status` to Sales Invoice, call `sync.sync_transport` when transport changed)
- Produces test helpers reused by Task 3-5: `in_scope_invoices(limit=3) -> list[str]`, `ensure_transporter() -> str`, `fresh_log(invoice_name) -> Document`

- [ ] **Step 1: Write the failing tests**

````python
# file: chundakadan/chundakadan/doctype/dispatch_log/test_dispatch_log.py
# Copyright (c) 2026, Chundakadan and contributors
# For license information, please see license.txt

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate

from chundakadan.dispatch import constants as C
from chundakadan.dispatch.setup import ensure_dispatch_role, ensure_sales_invoice_field

# Tests use real submitted invoices on the site; don't generate ERPNext test records.
test_ignore = ["Sales Invoice", "Customer", "Supplier", "Company", "User"]

TRANSPORTER = "_Test Dispatch Transporter"


def in_scope_invoices(limit=3):
	"""Submitted Chundakadan Agencies invoices without an e-Waybill."""
	return frappe.get_all(
		"Sales Invoice",
		filters={
			"company": C.COMPANY,
			"docstatus": 1,
			"is_return": 0,
			"is_opening": ["!=", "Yes"],
			"ewaybill": ["is", "not set"],
		},
		pluck="name",
		order_by="posting_date desc",
		limit=limit,
	)


def ensure_transporter():
	if not frappe.db.exists("Supplier", TRANSPORTER):
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": TRANSPORTER,
				"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
				"is_transporter": 1,
			}
		).insert(ignore_permissions=True)
	return TRANSPORTER


def fresh_log(invoice_name):
	"""Delete any existing log for the invoice and create a new Pending one."""
	from chundakadan.dispatch.events import build_log

	for name in frappe.get_all("Dispatch Log", filters={"sales_invoice": invoice_name}, pluck="name"):
		frappe.delete_doc("Dispatch Log", name, force=1, ignore_permissions=True)
	return build_log(frappe.get_doc("Sales Invoice", invoice_name)).insert(ignore_permissions=True)


class TestDispatchLog(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		ensure_dispatch_role()
		ensure_sales_invoice_field()
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.invoices = in_scope_invoices()
		if not cls.invoices:
			raise unittest.SkipTest("no in-scope Sales Invoice on this site")
		cls.transporter = ensure_transporter()

	def _dispatch(self, log, **kw):
		log.transporter = kw.get("transporter", self.transporter)
		log.expected_delivery = kw.get("expected_delivery", "2 Days")
		log.vehicle_no = kw.get("vehicle_no", "KL10AB1234")
		log.dispatch_status = C.DISPATCHED
		log.save()
		return log

	def test_new_log_is_pending_and_mirrored_on_invoice(self):
		log = fresh_log(self.invoices[0])
		self.assertEqual(log.dispatch_status, C.PENDING)
		self.assertEqual(
			frappe.db.get_value("Sales Invoice", log.sales_invoice, "dispatch_status"), C.PENDING
		)

	def test_one_log_per_invoice(self):
		log = fresh_log(self.invoices[0])
		from chundakadan.dispatch.events import build_log

		with self.assertRaises(frappe.UniqueValidationError):
			build_log(frappe.get_doc("Sales Invoice", log.sales_invoice)).insert(ignore_permissions=True)

	def test_dispatch_requires_transporter(self):
		log = fresh_log(self.invoices[0])
		log.expected_delivery = "Next Day"
		log.dispatch_status = C.DISPATCHED
		with self.assertRaises(frappe.ValidationError):
			log.save()

	def test_dispatch_stamps_and_expected_date(self):
		log = self._dispatch(fresh_log(self.invoices[0]), expected_delivery="2 Days")
		self.assertEqual(log.dispatched_by, "Administrator")
		self.assertIsNotNone(log.dispatched_on)
		self.assertEqual(
			getdate(log.expected_delivery_date), add_days(getdate(log.dispatched_on), 2)
		)

	def test_changing_option_recomputes_date(self):
		log = self._dispatch(fresh_log(self.invoices[0]), expected_delivery="Next Day")
		log.expected_delivery = "After 2 Days"
		log.save()
		self.assertEqual(
			getdate(log.expected_delivery_date), add_days(getdate(log.dispatched_on), 3)
		)

	def test_invalid_transition_rejected(self):
		log = fresh_log(self.invoices[0])
		log.dispatch_status = C.DELIVERED
		with self.assertRaises(frappe.ValidationError):
			log.save()

	def test_delivered_after_dispatch_stamps_confirmation(self):
		log = self._dispatch(fresh_log(self.invoices[0]))
		log.dispatch_status = C.DELIVERED
		log.save()
		self.assertEqual(log.delivery_confirmed_by, "Administrator")
		self.assertIsNotNone(log.delivery_confirmed_on)

	def test_not_delivered_requires_date(self):
		log = self._dispatch(fresh_log(self.invoices[0]))
		log.dispatch_status = C.NOT_DELIVERED
		log.expected_delivery_date = None
		with self.assertRaises(frappe.ValidationError):
			log.save()

	def test_customer_pickup_closes_without_transporter(self):
		log = fresh_log(self.invoices[0])
		log.dispatch_status = C.PICKUP
		log.save()
		self.assertIsNotNone(log.delivery_confirmed_on)
		log.dispatch_status = C.DISPATCHED
		with self.assertRaises(frappe.ValidationError):
			log.save()

	def test_transport_copied_to_invoice_without_ewaybill(self):
		log = self._dispatch(fresh_log(self.invoices[0]), vehicle_no="KL10XY9999")
		invoice = frappe.db.get_value(
			"Sales Invoice", log.sales_invoice, ["transporter", "vehicle_no", "dispatch_status"], as_dict=True
		)
		self.assertEqual(invoice.transporter, self.transporter)
		self.assertEqual(invoice.vehicle_no, "KL10XY9999")
		self.assertEqual(invoice.dispatch_status, C.DISPATCHED)
		self.assertEqual(frappe.db.get_value("Dispatch Log", log.name, "ewaybill_sync_status"), "Not Required")
````

- [ ] **Step 2: Create the DocType definition**

````python
# file: chundakadan/chundakadan/doctype/dispatch_log/__init__.py

````

````json
# file: chundakadan/chundakadan/doctype/dispatch_log/dispatch_log.json
{
 "actions": [],
 "allow_rename": 0,
 "autoname": "DSP-.YY.-.#####",
 "creation": "2026-09-15 12:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "invoice_section",
  "sales_invoice",
  "company",
  "posting_date",
  "grand_total",
  "invoice_cancelled",
  "column_break_invoice",
  "customer",
  "customer_name",
  "contact_mobile",
  "status_section",
  "dispatch_status",
  "column_break_status",
  "pending_reason",
  "pending_remarks",
  "transport_section",
  "transporter",
  "transporter_name",
  "gst_transporter_id",
  "mode_of_transport",
  "column_break_transport",
  "vehicle_no",
  "lr_no",
  "lr_date",
  "driver_name",
  "dispatch_section",
  "dispatched_on",
  "dispatched_by",
  "column_break_dispatch",
  "expected_delivery",
  "expected_delivery_date",
  "delivery_section",
  "delivery_confirmed_on",
  "delivery_confirmed_by",
  "column_break_delivery",
  "delivery_remarks",
  "ewaybill_section",
  "ewaybill_sync_status",
  "ewaybill_sync_error"
 ],
 "fields": [
  {"fieldname": "invoice_section", "fieldtype": "Section Break", "label": "Invoice"},
  {"fieldname": "sales_invoice", "fieldtype": "Link", "label": "Sales Invoice", "options": "Sales Invoice", "reqd": 1, "unique": 1, "read_only": 1, "in_list_view": 1, "in_standard_filter": 1, "search_index": 1},
  {"fieldname": "company", "fieldtype": "Link", "label": "Company", "options": "Company", "read_only": 1},
  {"fieldname": "posting_date", "fieldtype": "Date", "label": "Invoice Date", "read_only": 1, "in_list_view": 1},
  {"fieldname": "grand_total", "fieldtype": "Currency", "label": "Grand Total", "read_only": 1},
  {"default": "0", "fieldname": "invoice_cancelled", "fieldtype": "Check", "label": "Invoice Cancelled", "read_only": 1},
  {"fieldname": "column_break_invoice", "fieldtype": "Column Break"},
  {"fieldname": "customer", "fieldtype": "Link", "label": "Customer", "options": "Customer", "read_only": 1, "in_standard_filter": 1},
  {"fieldname": "customer_name", "fieldtype": "Data", "label": "Customer Name", "read_only": 1, "in_list_view": 1},
  {"fieldname": "contact_mobile", "fieldtype": "Data", "label": "Customer Mobile", "read_only": 1},
  {"fieldname": "status_section", "fieldtype": "Section Break", "label": "Status"},
  {"default": "Pending", "fieldname": "dispatch_status", "fieldtype": "Select", "label": "Dispatch Status", "options": "Pending\nDispatched\nCustomer Pickup\nDelivered\nNot Delivered", "reqd": 1, "in_list_view": 1, "in_standard_filter": 1, "search_index": 1},
  {"fieldname": "column_break_status", "fieldtype": "Column Break"},
  {"fieldname": "pending_reason", "fieldtype": "Select", "label": "Pending Reason", "options": "\nStock Not Available\nPayment Pending\nCustomer Asked to Hold\nTransport Not Available\nOther"},
  {"fieldname": "pending_remarks", "fieldtype": "Small Text", "label": "Pending Remarks"},
  {"fieldname": "transport_section", "fieldtype": "Section Break", "label": "Transport"},
  {"fieldname": "transporter", "fieldtype": "Link", "label": "Transporter", "options": "Supplier", "in_standard_filter": 1, "link_filters": "[[\"Supplier\",\"is_transporter\",\"=\",1]]"},
  {"fetch_from": "transporter.supplier_name", "fieldname": "transporter_name", "fieldtype": "Data", "label": "Transporter Name", "read_only": 1},
  {"fetch_from": "transporter.gst_transporter_id", "fieldname": "gst_transporter_id", "fieldtype": "Data", "label": "GST Transporter ID", "read_only": 1},
  {"default": "Road", "fieldname": "mode_of_transport", "fieldtype": "Select", "label": "Mode of Transport", "options": "Road\nAir\nRail\nShip"},
  {"fieldname": "column_break_transport", "fieldtype": "Column Break"},
  {"fieldname": "vehicle_no", "fieldtype": "Data", "label": "Vehicle No"},
  {"fieldname": "lr_no", "fieldtype": "Data", "label": "Transport Receipt (LR) No"},
  {"fieldname": "lr_date", "fieldtype": "Date", "label": "LR Date"},
  {"fieldname": "driver_name", "fieldtype": "Data", "label": "Driver Name"},
  {"fieldname": "dispatch_section", "fieldtype": "Section Break", "label": "Dispatch"},
  {"fieldname": "dispatched_on", "fieldtype": "Datetime", "label": "Dispatched On", "read_only": 1},
  {"fieldname": "dispatched_by", "fieldtype": "Link", "label": "Dispatched By", "options": "User", "read_only": 1},
  {"fieldname": "column_break_dispatch", "fieldtype": "Column Break"},
  {"fieldname": "expected_delivery", "fieldtype": "Select", "label": "Expected Delivery", "options": "\nNext Day\n2 Days\nAfter 2 Days"},
  {"fieldname": "expected_delivery_date", "fieldtype": "Date", "label": "Expected Delivery Date", "in_list_view": 1},
  {"fieldname": "delivery_section", "fieldtype": "Section Break", "label": "Delivery Confirmation"},
  {"fieldname": "delivery_confirmed_on", "fieldtype": "Datetime", "label": "Confirmed On", "read_only": 1},
  {"fieldname": "delivery_confirmed_by", "fieldtype": "Link", "label": "Confirmed By", "options": "User", "read_only": 1},
  {"fieldname": "column_break_delivery", "fieldtype": "Column Break"},
  {"fieldname": "delivery_remarks", "fieldtype": "Small Text", "label": "Delivery Remarks"},
  {"collapsible": 1, "fieldname": "ewaybill_section", "fieldtype": "Section Break", "label": "e-Waybill Sync"},
  {"fieldname": "ewaybill_sync_status", "fieldtype": "Select", "label": "e-Waybill Sync Status", "options": "\nNot Required\nSynced\nFailed", "read_only": 1},
  {"fieldname": "ewaybill_sync_error", "fieldtype": "Small Text", "label": "e-Waybill Sync Error", "read_only": 1}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-09-15 12:00:00.000000",
 "modified_by": "Administrator",
 "module": "Chundakadan",
 "name": "Dispatch Log",
 "naming_rule": "Expression (old style)",
 "owner": "Administrator",
 "permissions": [
  {"create": 1, "email": 1, "export": 1, "print": 1, "read": 1, "report": 1, "role": "System Manager", "share": 1, "write": 1},
  {"export": 1, "print": 1, "read": 1, "report": 1, "role": "Dispatch User", "write": 1},
  {"export": 1, "print": 1, "read": 1, "report": 1, "role": "Accounts Manager"},
  {"export": 1, "print": 1, "read": 1, "report": 1, "role": "Sales Manager"},
  {"read": 1, "role": "Accounts User"},
  {"read": 1, "role": "Sales User"}
 ],
 "row_format": "Dynamic",
 "search_fields": "sales_invoice,customer_name",
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "title_field": "customer_name",
 "track_changes": 1
}
````

- [ ] **Step 3: Implement the controller**

````python
# file: chundakadan/chundakadan/doctype/dispatch_log/dispatch_log.py
# Copyright (c) 2026, Chundakadan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cstr, getdate, now_datetime

from chundakadan.dispatch import constants as C

# current status -> statuses it may move to
ALLOWED_TRANSITIONS = {
	C.PENDING: {C.PENDING, C.DISPATCHED, C.PICKUP},
	C.DISPATCHED: {C.DISPATCHED, C.DELIVERED, C.NOT_DELIVERED},
	C.NOT_DELIVERED: {C.NOT_DELIVERED, C.DELIVERED},
	C.PICKUP: {C.PICKUP},
	C.DELIVERED: {C.DELIVERED},
}


class DispatchLog(Document):
	def validate(self):
		previous = self.get_doc_before_save()
		old_status = previous.dispatch_status if previous else C.PENDING
		new_status = self.dispatch_status or C.PENDING

		if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
			frappe.throw(
				_("Dispatch status cannot change from {0} to {1}.").format(old_status, new_status)
			)

		if new_status == C.DISPATCHED:
			self._validate_dispatch(old_status, previous)
		elif new_status == C.NOT_DELIVERED and not self.expected_delivery_date:
			frappe.throw(_("Enter the new expected delivery date for Not Delivered."))

		if new_status in (C.PICKUP, C.DELIVERED, C.NOT_DELIVERED) and new_status != old_status:
			self.delivery_confirmed_on = now_datetime()
			self.delivery_confirmed_by = frappe.session.user

	def _validate_dispatch(self, old_status, previous):
		if not self.transporter:
			frappe.throw(_("Transporter is required to mark as Dispatched."))
		if not self.expected_delivery:
			frappe.throw(_("Expected Delivery is required to mark as Dispatched."))

		if old_status != C.DISPATCHED:
			self.dispatched_on = now_datetime()
			self.dispatched_by = frappe.session.user

		option_changed = previous is not None and self.expected_delivery != previous.expected_delivery
		date_unchanged = previous is not None and cstr(self.expected_delivery_date) == cstr(
			previous.expected_delivery_date
		)
		if not self.expected_delivery_date or (option_changed and date_unchanged):
			self.expected_delivery_date = add_days(
				getdate(self.dispatched_on), C.EXPECTED_DAYS[self.expected_delivery]
			)

	def on_update(self):
		if frappe.get_meta("Sales Invoice").has_field("dispatch_status"):
			frappe.db.set_value(
				"Sales Invoice",
				self.sales_invoice,
				"dispatch_status",
				self.dispatch_status,
				update_modified=False,
			)

		if self.dispatch_status == C.DISPATCHED and self._transport_changed():
			from chundakadan.dispatch.sync import sync_transport

			sync_transport(self)

	def _transport_changed(self):
		previous = self.get_doc_before_save()
		if not previous or previous.dispatch_status != C.DISPATCHED:
			return True
		return any(cstr(self.get(f)) != cstr(previous.get(f)) for f in C.TRANSPORT_FIELDS)
````

- [ ] **Step 4: Verify**

Sync the DocType on the test site: `bench --site erp.chundakadan.in execute frappe.reload_doc --args "['chundakadan','doctype','dispatch_log']"`. Then `cd ~/frappe-bench-15-india && bench --site erp.chundakadan.in run-tests --skip-test-records --module chundakadan.chundakadan.doctype.dispatch_log.test_dispatch_log`. Expected before controller: failures; after Tasks 3-4 files exist: all 10 tests pass.

- [ ] **Step 5: Commit**

```bash
git add -A chundakadan && git commit -m "feat(dispatch): Dispatch Log doctype with status rules"
```

### Task 3: Sales Invoice events and backfill patch

**Files:**
- Create/Modify: `chundakadan/dispatch/events.py`
- Create/Modify: `chundakadan/patches/backfill_dispatch_logs.py`
- Create/Modify: `chundakadan/dispatch/test_dispatch.py (event tests)`


**Interfaces:**
- Consumes: constants; DocType `Dispatch Log` (Task 2)
- Produces: `is_in_scope(invoice) -> bool`, `build_log(invoice) -> Document` (unsaved), `create_dispatch_log(doc, method=None)`, `mark_invoice_cancelled(doc, method=None)`, `backfill_dispatch_logs(from_date=BACKFILL_FROM) -> int`

- [ ] **Step 1: Write the failing tests (the full test module; event tests are test_is_in_scope, test_create_dispatch_log_is_idempotent, test_create_skips_out_of_scope_invoice, test_mark_invoice_cancelled, test_backfill_creates_missing_logs)**

````python
# file: chundakadan/dispatch/test_dispatch.py
"""Tests for dispatch events, transport sync and page API."""

from unittest import SkipTest
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from chundakadan.chundakadan.doctype.dispatch_log.test_dispatch_log import (
	ensure_transporter,
	fresh_log,
	in_scope_invoices,
)
from chundakadan.dispatch import api, constants as C
from chundakadan.dispatch.events import (
	backfill_dispatch_logs,
	create_dispatch_log,
	is_in_scope,
	mark_invoice_cancelled,
)
from chundakadan.dispatch.setup import ensure_dispatch_role, ensure_sales_invoice_field
from chundakadan.dispatch.sync import sync_transport

E_WAYBILL = "india_compliance.gst_india.utils.e_waybill"


class TestDispatch(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		ensure_dispatch_role()
		ensure_sales_invoice_field()
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.invoices = in_scope_invoices()
		if not cls.invoices:
			raise SkipTest("no in-scope Sales Invoice on this site")
		cls.transporter = ensure_transporter()

	def tearDown(self):
		frappe.set_user("Administrator")

	# ---- events -------------------------------------------------------

	def test_is_in_scope(self):
		base = {"company": C.COMPANY, "docstatus": 1, "is_return": 0, "is_opening": "No"}
		self.assertTrue(is_in_scope(frappe._dict(base)))
		self.assertFalse(is_in_scope(frappe._dict(base, company="Chundakadan Home Stop")))
		self.assertFalse(is_in_scope(frappe._dict(base, is_return=1)))
		self.assertFalse(is_in_scope(frappe._dict(base, is_opening="Yes")))
		self.assertFalse(is_in_scope(frappe._dict(base, docstatus=2)))

	def test_create_dispatch_log_is_idempotent(self):
		name = self.invoices[0]
		frappe.db.delete("Dispatch Log", {"sales_invoice": name})
		invoice = frappe.get_doc("Sales Invoice", name)
		create_dispatch_log(invoice)
		create_dispatch_log(invoice)
		self.assertEqual(frappe.db.count("Dispatch Log", {"sales_invoice": name}), 1)

	def test_create_skips_out_of_scope_invoice(self):
		name = self.invoices[0]
		frappe.db.delete("Dispatch Log", {"sales_invoice": name})
		invoice = frappe.get_doc("Sales Invoice", name)
		invoice.company = "Chundakadan Home Stop"
		create_dispatch_log(invoice)
		self.assertEqual(frappe.db.count("Dispatch Log", {"sales_invoice": name}), 0)

	def test_mark_invoice_cancelled(self):
		log = fresh_log(self.invoices[0])
		mark_invoice_cancelled(frappe.get_doc("Sales Invoice", log.sales_invoice))
		self.assertEqual(frappe.db.get_value("Dispatch Log", log.name, "invoice_cancelled"), 1)

	def test_backfill_creates_missing_logs(self):
		filters = {
			"company": C.COMPANY,
			"docstatus": 1,
			"is_return": 0,
			"is_opening": ["!=", "Yes"],
			"posting_date": [">=", C.BACKFILL_FROM],
		}
		names = frappe.get_all("Sales Invoice", filters=filters, pluck="name")
		frappe.db.delete("Dispatch Log", {"sales_invoice": ["in", names or [""]]})
		created = backfill_dispatch_logs()
		self.assertEqual(created, len(names))
		self.assertEqual(backfill_dispatch_logs(), 0)

	# ---- sync ---------------------------------------------------------

	def _dispatched_log_with_ewaybill(self, gst_transporter_id=None):
		log = fresh_log(self.invoices[0])
		frappe.db.set_value("Sales Invoice", log.sales_invoice, "ewaybill", "331000000001", update_modified=False)
		log.transporter = self.transporter
		log.gst_transporter_id = gst_transporter_id
		log.vehicle_no = "KL10AB1234"
		log.lr_no = "LR-1"
		log.expected_delivery = "Next Day"
		log.dispatch_status = C.DISPATCHED
		return log

	def test_sync_with_ewaybill_updates_vehicle_on_portal(self):
		log = self._dispatched_log_with_ewaybill()
		with patch(f"{E_WAYBILL}.update_vehicle_info") as vehicle, patch(f"{E_WAYBILL}.update_transporter") as transporter:
			log.save()
		vehicle.assert_called_once()
		values = vehicle.call_args.kwargs["values"]
		self.assertEqual(values["vehicle_no"], "KL10AB1234")
		self.assertEqual(values["lr_no"], "LR-1")
		transporter.assert_not_called()  # no GST transporter id
		self.assertEqual(frappe.db.get_value("Sales Invoice", log.sales_invoice, "transporter"), self.transporter)
		self.assertEqual(frappe.db.get_value("Dispatch Log", log.name, "ewaybill_sync_status"), "Synced")

	def test_sync_calls_update_transporter_when_id_present(self):
		log = self._dispatched_log_with_ewaybill()
		# Every save/sync of a log whose invoice has an e-Waybill must stay patched:
		# unpatched calls would reach the live e-Waybill portal.
		with patch(f"{E_WAYBILL}.update_vehicle_info"), patch(f"{E_WAYBILL}.update_transporter") as transporter:
			log.save()
			transporter.reset_mock()
			# fetch_from blanks the id on save, so set it after saving and sync directly
			log.gst_transporter_id = "32AAGFC3363E1ZX"
			sync_transport(log)
		transporter.assert_called_once()
		self.assertEqual(transporter.call_args.kwargs["values"]["gst_transporter_id"], "32AAGFC3363E1ZX")

	def test_sync_failure_marks_failed(self):
		log = self._dispatched_log_with_ewaybill()
		with patch(f"{E_WAYBILL}.update_vehicle_info", side_effect=Exception("portal down")):
			log.save()
		row = frappe.db.get_value("Dispatch Log", log.name, ["dispatch_status", "ewaybill_sync_status", "ewaybill_sync_error"], as_dict=True)
		self.assertEqual(row.dispatch_status, C.DISPATCHED)
		self.assertEqual(row.ewaybill_sync_status, "Failed")
		self.assertIn("portal down", row.ewaybill_sync_error)

	# ---- api ----------------------------------------------------------

	def test_api_full_flow(self):
		log = fresh_log(self.invoices[0])
		api.set_pending_reason(log.name, "Payment Pending", "waiting for cheque")
		self.assertEqual(frappe.db.get_value("Dispatch Log", log.name, "pending_reason"), "Payment Pending")

		pending = api.get_logs("pending", filters={"search": log.sales_invoice})
		self.assertIn(log.name, [r.name for r in pending])
		self.assertIn("days_pending", pending[0])

		result = api.mark_dispatched(log.name, self.transporter, "Next Day", vehicle_no="KL10AB1234")
		self.assertEqual(result["dispatch_status"], C.DISPATCHED)

		with self.assertRaises(frappe.ValidationError):
			api.confirm_delivery(log.name, delivered=0)

		api.confirm_delivery(log.name, delivered=0, remarks="shop closed", new_expected_date=nowdate())
		followup = api.get_logs("followup", filters={"search": log.sales_invoice})
		self.assertIn(log.name, [r.name for r in followup])

		api.confirm_delivery(log.name, delivered="true", remarks="received")
		self.assertEqual(frappe.db.get_value("Dispatch Log", log.name, "dispatch_status"), C.DELIVERED)
		counts = api.get_counts(filters={"search": log.sales_invoice})
		self.assertEqual(counts["delivered_today"], 1)

	def test_api_rejects_invalid_reason_and_wrong_status(self):
		log = fresh_log(self.invoices[0])
		with self.assertRaises(frappe.ValidationError):
			api.set_pending_reason(log.name, "Rain")
		with self.assertRaises(frappe.ValidationError):
			api.confirm_delivery(log.name, delivered=1)

	def test_api_customer_pickup(self):
		log = fresh_log(self.invoices[0])
		api.mark_customer_pickup(log.name, "collected at counter")
		delivered = api.get_logs("delivered", filters={"search": log.sales_invoice})
		self.assertIn(log.name, [r.name for r in delivered])

	def test_api_blocks_cancelled_invoice(self):
		log = fresh_log(self.invoices[0])
		frappe.db.set_value("Dispatch Log", log.name, "invoice_cancelled", 1)
		with self.assertRaises(frappe.ValidationError):
			api.mark_customer_pickup(log.name)

	def test_api_requires_permission(self):
		log = fresh_log(self.invoices[0])
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			api.get_counts()
		with self.assertRaises(frappe.PermissionError):
			api.mark_customer_pickup(log.name)
````

- [ ] **Step 2: Implement events and the backfill patch**

````python
# file: chundakadan/dispatch/events.py
"""Sales Invoice hooks that create and maintain Dispatch Logs."""

import frappe

from chundakadan.dispatch import constants as C


def is_in_scope(invoice) -> bool:
	return (
		invoice.get("company") == C.COMPANY
		and invoice.get("docstatus") == 1
		and not invoice.get("is_return")
		and invoice.get("is_opening") != "Yes"
	)


def _contact_mobile(invoice) -> str:
	mobile = invoice.get("contact_mobile")
	if not mobile and invoice.get("customer_address"):
		mobile = frappe.db.get_value("Address", invoice.get("customer_address"), "phone")
	return mobile or ""


def build_log(invoice):
	return frappe.get_doc(
		{
			"doctype": "Dispatch Log",
			"sales_invoice": invoice.name,
			"company": invoice.company,
			"customer": invoice.customer,
			"customer_name": invoice.customer_name,
			"contact_mobile": _contact_mobile(invoice),
			"posting_date": invoice.posting_date,
			"grand_total": invoice.grand_total,
			"dispatch_status": C.PENDING,
		}
	)


def create_dispatch_log(doc, method=None):
	"""on_submit on Sales Invoice. Never blocks the submit."""
	if not is_in_scope(doc):
		return
	try:
		if frappe.db.exists("Dispatch Log", {"sales_invoice": doc.name}):
			return
		build_log(doc).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title=f"Dispatch Log creation failed for {doc.name}")


def mark_invoice_cancelled(doc, method=None):
	"""on_cancel on Sales Invoice."""
	name = frappe.db.get_value("Dispatch Log", {"sales_invoice": doc.name})
	if name:
		frappe.db.set_value("Dispatch Log", name, "invoice_cancelled", 1)


def backfill_dispatch_logs(from_date=C.BACKFILL_FROM) -> int:
	names = frappe.get_all(
		"Sales Invoice",
		filters={
			"company": C.COMPANY,
			"docstatus": 1,
			"is_return": 0,
			"is_opening": ["!=", "Yes"],
			"posting_date": [">=", from_date],
		},
		pluck="name",
	)
	created = 0
	for name in names:
		if frappe.db.exists("Dispatch Log", {"sales_invoice": name}):
			continue
		build_log(frappe.get_doc("Sales Invoice", name)).insert(ignore_permissions=True)
		created += 1
	return created
````

````python
# file: chundakadan/patches/backfill_dispatch_logs.py
from chundakadan.dispatch.events import backfill_dispatch_logs
from chundakadan.dispatch.setup import ensure_dispatch_role, ensure_sales_invoice_field


def execute():
	# Patches run before after_migrate, so make sure the role and the Sales
	# Invoice field exist before logs mirror their status onto invoices.
	ensure_dispatch_role()
	ensure_sales_invoice_field()
	backfill_dispatch_logs()
````

- [ ] **Step 3: Verify**

`cd ~/frappe-bench-15-india && bench --site erp.chundakadan.in run-tests --skip-test-records --module chundakadan.dispatch.test_dispatch`. Expected: event tests pass (sync/api tests pass after Tasks 4-5).

- [ ] **Step 4: Commit**

```bash
git add -A chundakadan && git commit -m "feat(dispatch): create logs on invoice submit, backfill patch"
```

### Task 4: Transport sync to Sales Invoice and e-Waybill

**Files:**
- Create/Modify: `chundakadan/dispatch/sync.py`


**Interfaces:**
- Consumes: constants; India Compliance `india_compliance.gst_india.utils.e_waybill.update_transporter(doctype, docname, values)` and `update_vehicle_info(doctype, docname, values)` (values keys: vehicle_no, lr_no, lr_date, mode_of_transport, gst_vehicle_type, place_of_change, state, reason in {First Time, Others, Due to Break Down, Due to Trans Shipment}, remark)
- Produces: `sync_transport(log) -> str` returning and storing `ewaybill_sync_status` in {Not Required, Synced, Failed}

- [ ] **Step 1: Implement sync (tests already in test_dispatch.py: test_sync_with_ewaybill_updates_vehicle_on_portal, test_sync_calls_update_transporter_when_id_present, test_sync_failure_marks_failed — all portal calls mocked)**

````python
# file: chundakadan/dispatch/sync.py
"""Copy dispatch transport details to the Sales Invoice and its e-Waybill."""

import frappe
from frappe.utils import cstr

from chundakadan.dispatch import constants as C


def _as_administrator(fn, **kwargs):
	# India Compliance checks "submit" permission on the invoice; the Dispatch
	# User only has read. The API layer has already checked Dispatch Log write.
	user = frappe.session.user
	try:
		frappe.set_user("Administrator")
		return fn(**kwargs)
	finally:
		frappe.set_user(user)


def _place_of_dispatch(invoice):
	city, state = None, None
	if invoice.company_address:
		city, state = frappe.db.get_value("Address", invoice.company_address, ["city", "state"]) or (None, None)
	return city or "Kerala", state or "Kerala"


def _sync_ewaybill(log, invoice):
	from india_compliance.gst_india.utils import e_waybill

	if log.gst_transporter_id:
		_as_administrator(
			e_waybill.update_transporter,
			doctype="Sales Invoice",
			docname=invoice.name,
			values={
				"transporter": log.transporter,
				"gst_transporter_id": log.gst_transporter_id,
				"update_e_waybill_data": 0,
			},
		)
	else:
		frappe.db.set_value(
			"Sales Invoice",
			invoice.name,
			{"transporter": log.transporter, "transporter_name": log.transporter_name},
			update_modified=False,
		)

	if log.vehicle_no or log.lr_no:
		place, state = _place_of_dispatch(invoice)
		_as_administrator(
			e_waybill.update_vehicle_info,
			doctype="Sales Invoice",
			docname=invoice.name,
			values={
				"vehicle_no": log.vehicle_no or "",
				"lr_no": log.lr_no,
				"lr_date": log.lr_date,
				"mode_of_transport": log.mode_of_transport or "Road",
				"gst_vehicle_type": "Regular",
				"place_of_change": place,
				"state": state,
				"reason": "Others" if invoice.vehicle_no else "First Time",
				"remark": "Updated from Dispatch",
			},
		)

	frappe.db.set_value(
		"Sales Invoice", invoice.name, "driver_name", log.driver_name, update_modified=False
	)


def sync_transport(log) -> str:
	"""Returns the resulting ewaybill_sync_status and stores it on the log."""
	invoice = frappe.db.get_value(
		"Sales Invoice",
		log.sales_invoice,
		["name", "ewaybill", "vehicle_no", "company_address"],
		as_dict=True,
	)
	if not invoice:
		return log.ewaybill_sync_status

	try:
		if invoice.ewaybill:
			_sync_ewaybill(log, invoice)
			status = "Synced"
		else:
			frappe.db.set_value(
				"Sales Invoice",
				invoice.name,
				{field: log.get(field) for field in C.TRANSPORT_FIELDS},
				update_modified=False,
			)
			status = "Not Required"
		error = ""
	except Exception as e:
		frappe.log_error(title=f"Dispatch transport sync failed for {log.sales_invoice}")
		status, error = "Failed", cstr(e)[:1000]

	log.db_set({"ewaybill_sync_status": status, "ewaybill_sync_error": error}, update_modified=False)
	return status
````

- [ ] **Step 2: Verify**

`cd ~/frappe-bench-15-india && bench --site erp.chundakadan.in run-tests --skip-test-records --module chundakadan.dispatch.test_dispatch` and `cd ~/frappe-bench-15-india && bench --site erp.chundakadan.in run-tests --skip-test-records --module chundakadan.chundakadan.doctype.dispatch_log.test_dispatch_log`. Expected: sync tests pass. Never run a sync against an invoice with a real e-Waybill unpatched.

- [ ] **Step 3: Commit**

```bash
git add -A chundakadan && git commit -m "feat(dispatch): sync transport to invoice and e-Waybill"
```

### Task 5: Dispatch page API

**Files:**
- Create/Modify: `chundakadan/dispatch/api.py`


**Interfaces:**
- Consumes: constants, DocType, `sync.sync_transport`
- Produces (whitelisted, `chundakadan.dispatch.api.*`): `get_counts(filters=None) -> {pending, followup, dispatched, not_delivered, delivered_today}`, `get_logs(tab, filters=None, start=0, page_length=50) -> list[dict]` (tab in pending/followup/dispatched/not_delivered/delivered; rows include days_pending), `set_pending_reason(log, reason, remarks=None)`, `mark_dispatched(log, transporter, expected_delivery, vehicle_no=None, lr_no=None, lr_date=None, driver_name=None, mode_of_transport='Road', expected_delivery_date=None)`, `update_transport(...same...)`, `mark_customer_pickup(log, remarks=None)`, `confirm_delivery(log, delivered, remarks=None, new_expected_date=None)`, `retry_sync(log)`; actions return `{name, dispatch_status, ewaybill_sync_status}`. filters keys: from_date, to_date, customer, transporter, search

- [ ] **Step 1: Implement the API (tests in test_dispatch.py: test_api_full_flow, test_api_rejects_invalid_reason_and_wrong_status, test_api_customer_pickup, test_api_blocks_cancelled_invoice, test_api_requires_permission)**

````python
# file: chundakadan/dispatch/api.py
"""Whitelisted methods behind the Dispatch page."""

import frappe
from frappe import _
from frappe.utils import cint, date_diff, nowdate

from chundakadan.dispatch import constants as C
from chundakadan.dispatch.sync import sync_transport

LIST_FIELDS = [
	"name",
	"sales_invoice",
	"posting_date",
	"customer",
	"customer_name",
	"contact_mobile",
	"grand_total",
	"dispatch_status",
	"pending_reason",
	"pending_remarks",
	"transporter",
	"transporter_name",
	"gst_transporter_id",
	"vehicle_no",
	"lr_no",
	"lr_date",
	"driver_name",
	"mode_of_transport",
	"dispatched_on",
	"expected_delivery",
	"expected_delivery_date",
	"delivery_confirmed_on",
	"delivery_confirmed_by",
	"delivery_remarks",
	"ewaybill_sync_status",
	"ewaybill_sync_error",
]

TAB_ORDER = {
	"pending": "posting_date asc",
	"followup": "expected_delivery_date asc",
	"dispatched": "dispatched_on desc",
	"not_delivered": "expected_delivery_date asc",
	"delivered": "delivery_confirmed_on desc",
}


def _base_filters(filters):
	filters = frappe.parse_json(filters) if filters else {}
	conditions = [["invoice_cancelled", "=", 0]]
	if filters.get("from_date"):
		conditions.append(["posting_date", ">=", filters["from_date"]])
	if filters.get("to_date"):
		conditions.append(["posting_date", "<=", filters["to_date"]])
	if filters.get("customer"):
		conditions.append(["customer", "=", filters["customer"]])
	if filters.get("transporter"):
		conditions.append(["transporter", "=", filters["transporter"]])
	or_filters = None
	if filters.get("search"):
		like = f"%{filters['search']}%"
		or_filters = [["sales_invoice", "like", like], ["customer_name", "like", like]]
	return conditions, or_filters


def _tab_filters(tab):
	if tab == "pending":
		return [["dispatch_status", "=", C.PENDING]]
	if tab == "followup":
		return [
			["dispatch_status", "in", [C.DISPATCHED, C.NOT_DELIVERED]],
			["expected_delivery_date", "<=", nowdate()],
		]
	if tab == "dispatched":
		return [["dispatch_status", "=", C.DISPATCHED]]
	if tab == "not_delivered":
		return [["dispatch_status", "=", C.NOT_DELIVERED]]
	if tab == "delivered":
		return [["dispatch_status", "in", [C.DELIVERED, C.PICKUP]]]
	frappe.throw(_("Unknown tab {0}").format(tab))


def _count(conditions, or_filters):
	return len(frappe.get_all("Dispatch Log", filters=conditions, or_filters=or_filters, pluck="name"))


@frappe.whitelist()
def get_counts(filters=None):
	frappe.has_permission("Dispatch Log", "read", throw=True)
	base, or_filters = _base_filters(filters)
	counts = {tab: _count(base + _tab_filters(tab), or_filters) for tab in ("pending", "followup", "dispatched", "not_delivered")}
	counts["delivered_today"] = _count(
		base
		+ [
			["dispatch_status", "in", [C.DELIVERED, C.PICKUP]],
			["delivery_confirmed_on", ">=", nowdate()],
		],
		or_filters,
	)
	return counts


@frappe.whitelist()
def get_logs(tab, filters=None, start=0, page_length=50):
	frappe.has_permission("Dispatch Log", "read", throw=True)
	base, or_filters = _base_filters(filters)
	rows = frappe.get_all(
		"Dispatch Log",
		filters=base + _tab_filters(tab),
		or_filters=or_filters,
		fields=LIST_FIELDS,
		order_by=TAB_ORDER[tab],
		start=cint(start),
		page_length=cint(page_length) or 50,
	)
	today = nowdate()
	for row in rows:
		row["days_pending"] = date_diff(today, row.posting_date) if row.posting_date else 0
	return rows


def _get_log(log):
	doc = frappe.get_doc("Dispatch Log", log)
	doc.check_permission("write")
	if doc.invoice_cancelled:
		frappe.throw(_("Sales Invoice {0} is cancelled.").format(doc.sales_invoice))
	return doc


def _require_status(doc, *statuses):
	if doc.dispatch_status not in statuses:
		frappe.throw(
			_("{0} is {1}; this action needs status {2}.").format(
				doc.sales_invoice, doc.dispatch_status, " / ".join(statuses)
			)
		)


def _set_transport(doc, transporter, vehicle_no, lr_no, lr_date, driver_name, mode_of_transport):
	doc.transporter = transporter
	doc.vehicle_no = vehicle_no
	doc.lr_no = lr_no
	doc.lr_date = lr_date or None
	doc.driver_name = driver_name
	doc.mode_of_transport = mode_of_transport or "Road"
	supplier = frappe.db.get_value("Supplier", transporter, ["supplier_name", "gst_transporter_id"], as_dict=True) if transporter else None
	doc.transporter_name = supplier.supplier_name if supplier else None
	doc.gst_transporter_id = supplier.gst_transporter_id if supplier else None


def _result(doc):
	doc.reload()
	return {"name": doc.name, "dispatch_status": doc.dispatch_status, "ewaybill_sync_status": doc.ewaybill_sync_status}


@frappe.whitelist()
def set_pending_reason(log, reason, remarks=None):
	if reason not in C.PENDING_REASONS:
		frappe.throw(_("Invalid pending reason: {0}").format(reason))
	doc = _get_log(log)
	_require_status(doc, C.PENDING)
	doc.pending_reason = reason
	doc.pending_remarks = remarks
	doc.save()
	return _result(doc)


@frappe.whitelist()
def mark_dispatched(
	log,
	transporter,
	expected_delivery,
	vehicle_no=None,
	lr_no=None,
	lr_date=None,
	driver_name=None,
	mode_of_transport="Road",
	expected_delivery_date=None,
):
	doc = _get_log(log)
	_require_status(doc, C.PENDING)
	_set_transport(doc, transporter, vehicle_no, lr_no, lr_date, driver_name, mode_of_transport)
	doc.expected_delivery = expected_delivery
	doc.expected_delivery_date = expected_delivery_date or None
	doc.dispatch_status = C.DISPATCHED
	doc.save()
	return _result(doc)


@frappe.whitelist()
def update_transport(
	log,
	transporter,
	expected_delivery,
	vehicle_no=None,
	lr_no=None,
	lr_date=None,
	driver_name=None,
	mode_of_transport="Road",
	expected_delivery_date=None,
):
	doc = _get_log(log)
	_require_status(doc, C.DISPATCHED)
	_set_transport(doc, transporter, vehicle_no, lr_no, lr_date, driver_name, mode_of_transport)
	doc.expected_delivery = expected_delivery
	if expected_delivery_date:
		doc.expected_delivery_date = expected_delivery_date
	doc.save()
	return _result(doc)


@frappe.whitelist()
def mark_customer_pickup(log, remarks=None):
	doc = _get_log(log)
	_require_status(doc, C.PENDING)
	doc.dispatch_status = C.PICKUP
	doc.delivery_remarks = remarks
	doc.save()
	return _result(doc)


@frappe.whitelist()
def confirm_delivery(log, delivered, remarks=None, new_expected_date=None):
	delivered = bool(cint(frappe.parse_json(delivered) if isinstance(delivered, str) else delivered))
	doc = _get_log(log)
	_require_status(doc, C.DISPATCHED, C.NOT_DELIVERED)
	doc.delivery_remarks = remarks
	if delivered:
		doc.dispatch_status = C.DELIVERED
	else:
		if not new_expected_date:
			frappe.throw(_("Enter the new expected delivery date."))
		doc.dispatch_status = C.NOT_DELIVERED
		doc.expected_delivery_date = new_expected_date
	doc.save()
	return _result(doc)


@frappe.whitelist()
def retry_sync(log):
	doc = _get_log(log)
	_require_status(doc, C.DISPATCHED)
	sync_transport(doc)
	return _result(doc)
````

- [ ] **Step 2: Verify**

`cd ~/frappe-bench-15-india && bench --site erp.chundakadan.in run-tests --skip-test-records --module chundakadan.dispatch.test_dispatch`. Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add -A chundakadan && git commit -m "feat(dispatch): page API"
```

### Task 6: Dispatch desk page

**Files:**
- Create/Modify: `chundakadan/chundakadan/page/dispatch/__init__.py`
- Create/Modify: `chundakadan/chundakadan/page/dispatch/dispatch.json`
- Create/Modify: `chundakadan/chundakadan/page/dispatch/dispatch.js`


**Interfaces:**
- Consumes: Task 5 API method names and return shapes exactly as listed there.

- [ ] **Step 1: Create the page**

````python
# file: chundakadan/chundakadan/page/dispatch/__init__.py

````

````json
# file: chundakadan/chundakadan/page/dispatch/dispatch.json
{
 "content": null,
 "creation": "2026-09-15 12:00:00.000000",
 "docstatus": 0,
 "doctype": "Page",
 "idx": 0,
 "modified": "2026-09-15 12:00:00.000000",
 "modified_by": "Administrator",
 "module": "Chundakadan",
 "name": "dispatch",
 "owner": "Administrator",
 "page_name": "dispatch",
 "roles": [
  {"role": "Dispatch User"},
  {"role": "System Manager"},
  {"role": "Accounts Manager"},
  {"role": "Sales Manager"}
 ],
 "script": null,
 "standard": "Yes",
 "style": null,
 "system_page": 0,
 "title": "Dispatch"
}
````

````javascript
# file: chundakadan/chundakadan/page/dispatch/dispatch.js
// Dispatch board — spec: docs/superpowers/specs/2026-09-15-dispatch-tracking-design.md

frappe.pages["dispatch"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Dispatch"),
		single_column: true,
	});
	wrapper.dispatch_board = new DispatchBoard(page);
};

frappe.pages["dispatch"].on_page_show = function (wrapper) {
	if (wrapper.dispatch_board) wrapper.dispatch_board.refresh();
};

const DISPATCH_API = "chundakadan.dispatch.api";
const DISPATCH_PAGE_LENGTH = 50;
const EXPECTED_OPTIONS = ["Next Day", "2 Days", "After 2 Days"];
const PENDING_REASONS = [
	"Stock Not Available",
	"Payment Pending",
	"Customer Asked to Hold",
	"Transport Not Available",
	"Other",
];
const DISPATCH_CARDS = [
	{ key: "pending", tab: "pending", label: __("Pending") },
	{ key: "followup", tab: "followup", label: __("Follow-up Today") },
	{ key: "dispatched", tab: "dispatched", label: __("Dispatched") },
	{ key: "not_delivered", tab: "not_delivered", label: __("Not Delivered") },
	{ key: "delivered_today", tab: "delivered", label: __("Delivered Today") },
];

function dsp_esc(value) {
	return frappe.utils.escape_html(value == null ? "" : String(value));
}

function dsp_date(value) {
	return value ? frappe.datetime.str_to_user(value) : "";
}

class DispatchBoard {
	constructor(page) {
		this.page = page;
		this.tab = "pending";
		this.filters = {};
		this.rows = [];
		this.can_write = (frappe.boot.user.can_write || []).includes("Dispatch Log");
		this.make_layout();
		this.make_filters();
		this.refresh();
	}

	make_layout() {
		this.page.set_secondary_action(__("Refresh"), () => this.refresh(), "refresh");
		this.$body = $(`
			<div class="dispatch-board">
				<style>
					.dispatch-board .dsp-cards { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }
					.dispatch-board .dsp-card { flex: 1 1 140px; border: 1px solid var(--border-color); border-radius: 8px;
						padding: 10px 12px; cursor: pointer; background: var(--card-bg); }
					.dispatch-board .dsp-card.active { border-color: var(--primary); box-shadow: 0 0 0 1px var(--primary); }
					.dispatch-board .dsp-count { font-size: 22px; font-weight: 600; }
					.dispatch-board .dsp-label { color: var(--text-muted); font-size: 12px; }
					.dispatch-board .dsp-filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
					.dispatch-board .dsp-filters .frappe-control { flex: 1 1 160px; margin-bottom: 0; }
					.dispatch-board .dsp-table-wrap { overflow-x: auto; }
					.dispatch-board table { width: 100%; font-size: 13px; border-collapse: collapse; }
					.dispatch-board th { white-space: nowrap; background: var(--subtle-fg); }
					.dispatch-board td, .dispatch-board th { padding: 6px 8px; border-bottom: 1px solid var(--border-color); vertical-align: top; }
					.dispatch-board tr.dsp-overdue td { background: var(--bg-red, #fff1f1); }
					.dispatch-board .dsp-actions { white-space: nowrap; }
					.dispatch-board .dsp-actions .btn { margin: 0 4px 4px 0; }
					.dispatch-board .dsp-empty, .dispatch-board .dsp-more { margin: 16px 0; text-align: center; color: var(--text-muted); }
				</style>
				<div class="dsp-cards"></div>
				<div class="dsp-filters"></div>
				<div class="dsp-table-wrap"></div>
				<div class="dsp-more"></div>
			</div>
		`).appendTo(this.page.body);

		this.$cards = this.$body.find(".dsp-cards");
		this.$table = this.$body.find(".dsp-table-wrap");
		this.$more = this.$body.find(".dsp-more");

		DISPATCH_CARDS.forEach((card) => {
			$(`<div class="dsp-card" data-tab="${card.tab}" data-key="${card.key}">
				<div class="dsp-count">0</div><div class="dsp-label">${card.label}</div>
			</div>`).appendTo(this.$cards);
		});
		this.$cards.on("click", ".dsp-card", (e) => {
			this.tab = $(e.currentTarget).data("tab");
			this.load_rows();
		});
		this.$table.on("click", "button[data-action]", (e) => {
			const $btn = $(e.currentTarget);
			const row = this.rows.find((r) => r.name === $btn.data("name"));
			if (row) this.run_action($btn.data("action"), row);
		});
		this.$more.on("click", "button", () => this.load_rows(true));
	}

	make_filters() {
		const $filters = this.$body.find(".dsp-filters");
		const make = (df) =>
			frappe.ui.form.make_control({
				parent: $("<div>").appendTo($filters),
				df: Object.assign({ change: () => this.on_filter_change() }, df),
				render_input: true,
			});
		this.controls = {
			from_date: make({ fieldtype: "Date", fieldname: "from_date", placeholder: __("Invoice From") }),
			to_date: make({ fieldtype: "Date", fieldname: "to_date", placeholder: __("Invoice To") }),
			customer: make({ fieldtype: "Link", fieldname: "customer", options: "Customer", placeholder: __("Customer") }),
			transporter: make({
				fieldtype: "Link",
				fieldname: "transporter",
				options: "Supplier",
				placeholder: __("Transporter"),
				get_query: () => ({ filters: { is_transporter: 1 } }),
			}),
			search: make({ fieldtype: "Data", fieldname: "search", placeholder: __("Invoice No / Customer Name") }),
		};
		Object.values(this.controls).forEach((c) => c.refresh());
	}

	on_filter_change() {
		clearTimeout(this.filter_timer);
		this.filter_timer = setTimeout(() => {
			const filters = {};
			Object.entries(this.controls).forEach(([key, control]) => {
				const value = control.get_value();
				if (value) filters[key] = value;
			});
			this.filters = filters;
			this.refresh();
		}, 300);
	}

	refresh() {
		this.load_counts();
		this.load_rows();
	}

	load_counts() {
		frappe.call({ method: `${DISPATCH_API}.get_counts`, args: { filters: this.filters } }).then((r) => {
			const counts = r.message || {};
			DISPATCH_CARDS.forEach((card) => {
				this.$cards.find(`[data-key="${card.key}"] .dsp-count`).text(counts[card.key] || 0);
			});
		});
	}

	load_rows(append = false) {
		this.$cards.find(".dsp-card").removeClass("active");
		this.$cards.find(`[data-tab="${this.tab}"]`).addClass("active");
		const start = append ? this.rows.length : 0;
		frappe
			.call({
				method: `${DISPATCH_API}.get_logs`,
				args: { tab: this.tab, filters: this.filters, start, page_length: DISPATCH_PAGE_LENGTH },
			})
			.then((r) => {
				const rows = r.message || [];
				this.rows = append ? this.rows.concat(rows) : rows;
				this.render_table();
				this.$more.html(
					rows.length === DISPATCH_PAGE_LENGTH
						? `<button class="btn btn-default btn-sm">${__("Load more")}</button>`
						: ""
				);
			});
	}

	columns() {
		const invoice = {
			label: __("Invoice"),
			html: (r) => `<a href="/app/sales-invoice/${encodeURIComponent(r.sales_invoice)}">${dsp_esc(r.sales_invoice)}</a>`,
		};
		const customer = { label: __("Customer"), html: (r) => dsp_esc(r.customer_name || r.customer) };
		const mobile = { label: __("Mobile"), html: (r) => dsp_esc(r.contact_mobile) };
		const transporter = { label: __("Transporter"), html: (r) => dsp_esc(r.transporter_name || r.transporter) };
		const expected = { label: __("Expected"), html: (r) => dsp_date(r.expected_delivery_date) };
		const remarks = { label: __("Remarks"), html: (r) => dsp_esc(r.delivery_remarks) };
		switch (this.tab) {
			case "pending":
				return [
					invoice,
					{ label: __("Date"), html: (r) => dsp_date(r.posting_date) },
					customer,
					{ label: __("Amount"), html: (r) => frappe.format(r.grand_total, { fieldtype: "Currency" }) },
					{ label: __("Days"), html: (r) => dsp_esc(r.days_pending) },
					{ label: __("Reason"), html: (r) => dsp_esc([r.pending_reason, r.pending_remarks].filter(Boolean).join(" — ")) },
				];
			case "followup":
				return [invoice, customer, mobile, transporter, expected, { label: __("Status"), html: (r) => dsp_esc(r.dispatch_status) }];
			case "dispatched":
				return [
					invoice,
					customer,
					transporter,
					{ label: __("Vehicle"), html: (r) => dsp_esc(r.vehicle_no) },
					{ label: __("LR No"), html: (r) => dsp_esc(r.lr_no) },
					{ label: __("Dispatched On"), html: (r) => dsp_esc(r.dispatched_on ? frappe.datetime.str_to_user(r.dispatched_on) : "") },
					expected,
					{
						label: __("e-Waybill"),
						html: (r) =>
							r.ewaybill_sync_status === "Failed"
								? `<span class="text-danger" title="${dsp_esc(r.ewaybill_sync_error)}">${__("Failed")}</span>`
								: dsp_esc(r.ewaybill_sync_status),
					},
				];
			case "not_delivered":
				return [invoice, customer, mobile, remarks, expected];
			default:
				return [
					invoice,
					customer,
					{ label: __("Status"), html: (r) => dsp_esc(r.dispatch_status) },
					{ label: __("Confirmed On"), html: (r) => dsp_esc(r.delivery_confirmed_on ? frappe.datetime.str_to_user(r.delivery_confirmed_on) : "") },
					{ label: __("Confirmed By"), html: (r) => dsp_esc(r.delivery_confirmed_by) },
					remarks,
				];
		}
	}

	actions(row) {
		if (!this.can_write) return [];
		switch (this.tab) {
			case "pending":
				return [
					["dispatch", __("Dispatch"), "btn-primary"],
					["reason", __("Reason"), "btn-default"],
					["pickup", __("Customer Pickup"), "btn-default"],
				];
			case "followup":
				return [
					["delivered", __("Delivered"), "btn-primary"],
					["not_delivered", __("Not Delivered"), "btn-default"],
				];
			case "dispatched": {
				const list = [
					["confirm", __("Confirm Delivery"), "btn-primary"],
					["edit_transport", __("Edit Transport"), "btn-default"],
				];
				if (row.ewaybill_sync_status === "Failed") list.push(["retry", __("Retry Sync"), "btn-danger"]);
				return list;
			}
			case "not_delivered":
				return [
					["delivered", __("Delivered"), "btn-primary"],
					["not_delivered", __("Reschedule"), "btn-default"],
				];
			default:
				return [];
		}
	}

	render_table() {
		if (!this.rows.length) {
			this.$table.html(`<div class="dsp-empty">${__("Nothing here")}</div>`);
			return;
		}
		const columns = this.columns();
		const with_actions = this.can_write && this.tab !== "delivered";
		const head = columns.map((c) => `<th>${c.label}</th>`).join("") + (with_actions ? `<th>${__("Actions")}</th>` : "");
		const body = this.rows
			.map((row) => {
				const overdue = this.tab === "pending" && row.days_pending > 2 ? "dsp-overdue" : "";
				const cells = columns.map((c) => `<td>${c.html(row)}</td>`).join("");
				const buttons = this.actions(row)
					.map(([action, label, cls]) => `<button class="btn btn-xs ${cls}" data-action="${action}" data-name="${dsp_esc(row.name)}">${label}</button>`)
					.join("");
				return `<tr class="${overdue}">${cells}${with_actions ? `<td class="dsp-actions">${buttons}</td>` : ""}</tr>`;
			})
			.join("");
		this.$table.html(`<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`);
	}

	call(method, args, message) {
		return frappe.call({ method: `${DISPATCH_API}.${method}`, args, freeze: true }).then((r) => {
			const result = r.message || {};
			if (result.ewaybill_sync_status === "Failed") {
				frappe.msgprint({ title: __("e-Waybill not updated"), indicator: "orange", message: __("Saved, but the e-Waybill update failed. Use Retry Sync.") });
			} else {
				frappe.show_alert({ message, indicator: "green" });
			}
			this.refresh();
		});
	}

	run_action(action, row) {
		const handlers = {
			dispatch: () => this.transport_dialog(row, "mark_dispatched"),
			edit_transport: () => this.transport_dialog(row, "update_transport"),
			reason: () => this.reason_dialog(row),
			pickup: () => this.pickup_dialog(row),
			delivered: () => this.delivered_dialog(row),
			not_delivered: () => this.not_delivered_dialog(row),
			confirm: () => this.confirm_dialog(row),
			retry: () => this.call("retry_sync", { log: row.name }, __("Sync retried")),
		};
		handlers[action]();
	}

	transport_dialog(row, method) {
		const dialog = new frappe.ui.Dialog({
			title: `${method === "mark_dispatched" ? __("Dispatch") : __("Edit Transport")} — ${row.sales_invoice}`,
			fields: [
				{ fieldtype: "Link", fieldname: "transporter", label: __("Transporter"), options: "Supplier", reqd: 1, default: row.transporter, get_query: () => ({ filters: { is_transporter: 1 } }) },
				{ fieldtype: "Data", fieldname: "vehicle_no", label: __("Vehicle No"), default: row.vehicle_no },
				{ fieldtype: "Data", fieldname: "lr_no", label: __("LR No"), default: row.lr_no },
				{ fieldtype: "Date", fieldname: "lr_date", label: __("LR Date"), default: row.lr_date },
				{ fieldtype: "Column Break" },
				{ fieldtype: "Data", fieldname: "driver_name", label: __("Driver Name"), default: row.driver_name },
				{ fieldtype: "Select", fieldname: "mode_of_transport", label: __("Mode of Transport"), options: "Road\nAir\nRail\nShip", default: row.mode_of_transport || "Road" },
				{ fieldtype: "Select", fieldname: "expected_delivery", label: __("Expected Delivery"), options: EXPECTED_OPTIONS.join("\n"), reqd: 1, default: row.expected_delivery || "Next Day" },
				{ fieldtype: "Date", fieldname: "expected_delivery_date", label: __("Expected Delivery Date"), default: row.expected_delivery_date, description: __("Leave blank to calculate from the option") },
			],
			primary_action_label: __("Save"),
			primary_action: (values) => {
				dialog.hide();
				this.call(method, Object.assign({ log: row.name }, values), __("Dispatch updated"));
			},
		});
		dialog.show();
	}

	reason_dialog(row) {
		const dialog = new frappe.ui.Dialog({
			title: `${__("Pending Reason")} — ${row.sales_invoice}`,
			fields: [
				{ fieldtype: "Select", fieldname: "reason", label: __("Reason"), options: PENDING_REASONS.join("\n"), reqd: 1, default: row.pending_reason },
				{ fieldtype: "Small Text", fieldname: "remarks", label: __("Remarks"), default: row.pending_remarks },
			],
			primary_action_label: __("Save"),
			primary_action: (values) => {
				dialog.hide();
				this.call("set_pending_reason", Object.assign({ log: row.name }, values), __("Reason saved"));
			},
		});
		dialog.show();
	}

	pickup_dialog(row) {
		const dialog = new frappe.ui.Dialog({
			title: `${__("Customer Pickup")} — ${row.sales_invoice}`,
			fields: [{ fieldtype: "Small Text", fieldname: "remarks", label: __("Remarks") }],
			primary_action_label: __("Mark Picked Up"),
			primary_action: (values) => {
				dialog.hide();
				this.call("mark_customer_pickup", { log: row.name, remarks: values.remarks }, __("Marked as customer pickup"));
			},
		});
		dialog.show();
	}

	delivered_dialog(row) {
		const dialog = new frappe.ui.Dialog({
			title: `${__("Delivered")} — ${row.sales_invoice}`,
			fields: [{ fieldtype: "Small Text", fieldname: "remarks", label: __("Remarks") }],
			primary_action_label: __("Confirm Delivered"),
			primary_action: (values) => {
				dialog.hide();
				this.call("confirm_delivery", { log: row.name, delivered: 1, remarks: values.remarks }, __("Delivery confirmed"));
			},
		});
		dialog.show();
	}

	not_delivered_dialog(row) {
		const dialog = new frappe.ui.Dialog({
			title: `${__("Not Delivered")} — ${row.sales_invoice}`,
			fields: [
				{ fieldtype: "Date", fieldname: "new_expected_date", label: __("New Expected Delivery Date"), reqd: 1 },
				{ fieldtype: "Small Text", fieldname: "remarks", label: __("Remarks"), reqd: 1 },
			],
			primary_action_label: __("Save"),
			primary_action: (values) => {
				dialog.hide();
				this.call("confirm_delivery", Object.assign({ log: row.name, delivered: 0 }, values), __("Rescheduled"));
			},
		});
		dialog.show();
	}

	confirm_dialog(row) {
		const dialog = new frappe.ui.Dialog({
			title: `${__("Confirm Delivery")} — ${row.sales_invoice}`,
			fields: [
				{ fieldtype: "Select", fieldname: "result", label: __("Result"), options: "Delivered\nNot Delivered", reqd: 1, default: "Delivered" },
				{ fieldtype: "Date", fieldname: "new_expected_date", label: __("New Expected Delivery Date"), depends_on: "eval:doc.result=='Not Delivered'", mandatory_depends_on: "eval:doc.result=='Not Delivered'" },
				{ fieldtype: "Small Text", fieldname: "remarks", label: __("Remarks") },
			],
			primary_action_label: __("Save"),
			primary_action: (values) => {
				dialog.hide();
				this.call(
					"confirm_delivery",
					{ log: row.name, delivered: values.result === "Delivered" ? 1 : 0, remarks: values.remarks, new_expected_date: values.new_expected_date },
					__("Delivery updated")
				);
			},
		});
		dialog.show();
	}
}
````

- [ ] **Step 2: Verify**

`node --check chundakadan/chundakadan/page/dispatch/dispatch.js` (syntax) and `bench --site erp.chundakadan.in execute frappe.reload_doc --args "['chundakadan','page','dispatch']"` (page syncs). Manual UI check happens on Frappe Cloud after deploy (old site is in maintenance mode).

- [ ] **Step 3: Commit**

```bash
git add -A chundakadan && git commit -m "feat(dispatch): Dispatch desk page"
```

### Task 7: Deploy

- [ ] **Step 1:** Run both test modules; all pass.
- [ ] **Step 2:** `git push upstream main`.
- [ ] **Step 3:** On Frappe Cloud: Apps → chundakadan → Update (migrate runs role setup, DocType/page sync, backfill patch, Sales Invoice field + permissions).
- [ ] **Step 4:** Business setup: mark transport partners as Supplier **Is Transporter**; assign **Dispatch User** to dispatch staff.
