# Display Tracking Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a desk-based custody-tracking system for supplier-owned display units in the `chundakadan` Frappe app — a `Display Unit` master with cached current-state, an immutable submittable `Display Movement` ledger, and a "Display View" workspace.

**Architecture:** Custody-ledger pattern (mirrors Stock Ledger Entry + Bin, no financial impact). `Display Movement` is the append-only source of truth; on submit its controller writes the resulting status/location/custody back onto the `Display Unit` cache. A pure-Python transition map validates every move. Reporting reads the cached fields.

**Tech Stack:** Frappe/ERPNext v15, Python, DocType JSON, FrappeTestCase, Workspace/Number Card/Dashboard Chart fixtures.

## Global Constraints

- App: `chundakadan`; new module **Display Tracking** (folder `display_tracking`).
- Bench: `frappe-bench-15-india`; test site: `erp.chundakadan.in` (or a dedicated test site).
- No financial/GL/stock/asset coupling — standalone operational DocTypes only.
- `Display Movement` is **submittable**; immutable once submitted; **delete permission granted to no role**.
- `Display Unit` current-state fields are **read-only in the UI** — written only by the movement controller.
- Naming via **Document Naming Rule**: `DISP-.YYYY.-.#####` (Display Unit), `DMV-.YYYY.-.######` (Display Movement).
- Statuses (exact strings): `At Supplier`, `In Warehouse`, `Reserved`, `In Transit`, `Installed at Customer`, `Returned`, `Damaged`, `Missing`, `Under Repair`, `Returned to Supplier`.
- Location types (exact strings): `Warehouse`, `Customer`, `Dealer`, `Retail Outlet`, `Service Center`, `Supplier`.
- Custodian links to **Employee**. Locations via **Dynamic Link** (Warehouse→Warehouse Rack, Customer/Dealer/Retail Outlet→Customer, Service Center→Display Service Center, Supplier→Supplier).
- Workspace **"Display View"**, `sequence_id = 3`, public, module Display Tracking.
- Run tests with: `bench --site erp.chundakadan.in run-tests --module <module.path>` (dev requirements + `allow_tests` must be enabled on the test site — see project preflight notes).

---

## File Structure

```
chundakadan/
  modules.txt                                   # + "Display Tracking"
  chundakadan/display_tracking/
    __init__.py
    doctype/
      display_type/                             # master
      display_service_center/                   # master
      display_unit/                             # master + cached state
      display_movement/                         # submittable ledger + controller
      display_movement_photo/                   # child table
    transitions.py                              # pure transition map (TDD)
    test_transitions.py                         # pure unit tests (no DB)
  chundakadan/hooks.py                          # + fixtures (Workspace, Number Card, Dashboard Chart, Document Naming Rule, Customer Group)
  fixtures/  (exported)                          # workspace + cards + charts + naming rules + customer groups
```

Responsibilities:
- `transitions.py` — the only place status/location rules live; pure functions, no Frappe DB. Consumed by the `Display Movement` controller.
- `display_movement.py` (controller) — orchestration only: read unit → call transition → write unit. No rules inline.
- `display_unit` — dumb master + cache; no business logic.

---

### Task 1: New module, masters, Customer Groups & naming rules

**Files:**
- Modify: `chundakadan/modules.txt` (append `Display Tracking`)
- Create: `chundakadan/chundakadan/display_tracking/__init__.py` (empty)
- Create: `chundakadan/chundakadan/display_tracking/doctype/__init__.py` (empty)
- Create: `chundakadan/chundakadan/display_tracking/doctype/display_type/display_type.json`
- Create: `chundakadan/chundakadan/display_tracking/doctype/display_type/display_type.py`
- Create: `chundakadan/chundakadan/display_tracking/doctype/display_type/__init__.py` (empty)
- Create: `chundakadan/chundakadan/display_tracking/doctype/display_service_center/display_service_center.json`
- Create: `chundakadan/chundakadan/display_tracking/doctype/display_service_center/display_service_center.py`
- Create: `chundakadan/chundakadan/display_tracking/doctype/display_service_center/__init__.py` (empty)

**Interfaces:**
- Produces: module `Display Tracking`; DocTypes `Display Type`, `Display Service Center`; Customer Groups `Dealer`, `Retail Outlet`; Document Naming Rules for `Display Unit` and `Display Movement`.

- [ ] **Step 1: Add the module**

Append a line to `chundakadan/modules.txt`:
```
Display Tracking
```
Create the empty `__init__.py` files listed above.

- [ ] **Step 2: Create `Display Type` DocType JSON**

`display_type.json`:
```json
{
 "actions": [], "allow_rename": 1, "autoname": "field:type_name",
 "creation": "2026-07-10 00:00:00", "doctype": "DocType", "engine": "InnoDB",
 "field_order": ["type_name", "description", "disabled"],
 "fields": [
  {"fieldname": "type_name", "fieldtype": "Data", "label": "Type Name", "reqd": 1, "unique": 1, "in_list_view": 1},
  {"fieldname": "description", "fieldtype": "Small Text", "label": "Description"},
  {"fieldname": "disabled", "fieldtype": "Check", "label": "Disabled"}
 ],
 "links": [], "module": "Display Tracking", "name": "Display Type",
 "owner": "Administrator", "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "Display Manager", "read": 1, "write": 1, "create": 1},
  {"role": "Warehouse User", "read": 1}
 ],
 "sort_field": "modified", "sort_order": "DESC", "track_changes": 1
}
```
`display_type.py`:
```python
import frappe
from frappe.model.document import Document


class DisplayType(Document):
    pass
```

- [ ] **Step 3: Create `Display Service Center` DocType JSON**

`display_service_center.json` (same shape):
```json
{
 "actions": [], "allow_rename": 1, "autoname": "field:service_center_name",
 "creation": "2026-07-10 00:00:00", "doctype": "DocType", "engine": "InnoDB",
 "field_order": ["service_center_name", "address", "disabled"],
 "fields": [
  {"fieldname": "service_center_name", "fieldtype": "Data", "label": "Service Center Name", "reqd": 1, "unique": 1, "in_list_view": 1},
  {"fieldname": "address", "fieldtype": "Small Text", "label": "Address"},
  {"fieldname": "disabled", "fieldtype": "Check", "label": "Disabled"}
 ],
 "links": [], "module": "Display Tracking", "name": "Display Service Center",
 "owner": "Administrator", "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "Display Manager", "read": 1, "write": 1, "create": 1},
  {"role": "Warehouse User", "read": 1}
 ],
 "sort_field": "modified", "sort_order": "DESC"
}
```
`display_service_center.py`:
```python
import frappe
from frappe.model.document import Document


class DisplayServiceCenter(Document):
    pass
```

- [ ] **Step 4: Create the two Roles (if absent) + Customer Groups + Naming Rules via a bench console one-off**

Run:
```bash
cd ~/frappe-bench-15-india && bench --site erp.chundakadan.in console
```
Paste (single lines; the roles Display Manager + Warehouse User must exist before the DocType JSONs referencing them migrate cleanly):
```python
for r in ["Display Manager", "Warehouse User"]:
    (not frappe.db.exists("Role", r)) and frappe.get_doc({"doctype":"Role","role_name":r,"desk_access":1}).insert(ignore_permissions=True)

for g in ["Dealer", "Retail Outlet"]:
    (not frappe.db.exists("Customer Group", g)) and frappe.get_doc({"doctype":"Customer Group","customer_group_name":g,"parent_customer_group":frappe.db.get_value("Customer Group",{"is_group":1},"name"),"is_group":0}).insert(ignore_permissions=True)

frappe.db.commit()
```
(These become fixtures in Task 8 so they reproduce on other sites; creating them here first unblocks migrate + tests.)

- [ ] **Step 5: Migrate and verify the module + masters exist**

Run:
```bash
cd ~/frappe-bench-15-india && bench --site erp.chundakadan.in migrate
```
Expected: migrate completes; `Display Type` and `Display Service Center` appear. Verify:
```bash
bench --site erp.chundakadan.in execute frappe.db.exists --kwargs '{"doctype":"DocType","name":"Display Type"}'
```
Expected: prints `Display Type`.

- [ ] **Step 6: Commit**

```bash
cd ~/frappe-bench-15-india/apps/chundakadan
git add chundakadan/modules.txt chundakadan/chundakadan/display_tracking
git commit -m "feat(display): add Display Tracking module + Display Type/Service Center masters"
```

---

### Task 2: `Display Unit` DocType

**Files:**
- Create: `chundakadan/chundakadan/display_tracking/doctype/display_unit/display_unit.json`
- Create: `chundakadan/chundakadan/display_tracking/doctype/display_unit/display_unit.py`
- Create: `chundakadan/chundakadan/display_tracking/doctype/display_unit/__init__.py` (empty)
- Create: `chundakadan/chundakadan/display_tracking/doctype/display_unit/test_display_unit.py`

**Interfaces:**
- Produces: DocType `Display Unit` with registration fields + read-only cached-state fields; `current_status` defaults to `At Supplier`; `barcode` mirrors `name`.
- Consumes: `Display Type`, `Display Service Center` (Task 1); `Supplier`, `Brand`, `Customer`, `Employee`, `Warehouse Rack` (existing).

- [ ] **Step 1: Write the failing test**

`test_display_unit.py`:
```python
import frappe
from frappe.tests.utils import FrappeTestCase


class TestDisplayUnit(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not frappe.db.exists("Display Type", "Cooler"):
            frappe.get_doc({"doctype": "Display Type", "type_name": "Cooler"}).insert()
        if not frappe.db.exists("Supplier", "_Test Display Supplier"):
            frappe.get_doc({"doctype": "Supplier", "supplier_name": "_Test Display Supplier",
                            "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")}).insert()

    def test_new_unit_defaults(self):
        unit = frappe.get_doc({
            "doctype": "Display Unit", "supplier": "_Test Display Supplier",
            "display_type": "Cooler", "description": "Chest cooler",
        }).insert()
        self.assertEqual(unit.current_status, "At Supplier")
        self.assertEqual(unit.current_location_type, "Supplier")
        self.assertEqual(unit.barcode, unit.name)
        self.assertTrue(unit.name.startswith("DISP-"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/frappe-bench-15-india && bench --site erp.chundakadan.in run-tests --module chundakadan.chundakadan.display_tracking.doctype.display_unit.test_display_unit`
Expected: FAIL — DocType `Display Unit` does not exist.

- [ ] **Step 3: Create the DocType JSON**

`display_unit.json` (naming rule set in Task 8; `autoname` left as `Prompt` fallback overridden by the Document Naming Rule — use `"autoname": "DISP-.YYYY.-.#####"` directly here so tests pass without the fixture):
```json
{
 "actions": [], "allow_rename": 0, "autoname": "DISP-.YYYY.-.#####",
 "creation": "2026-07-10 00:00:00", "doctype": "DocType", "engine": "InnoDB",
 "field_order": [
  "reg_section","supplier","display_type","brand","description","size_model","cb_reg","photo","barcode","remarks","is_active",
  "state_section","current_status","current_location_type","current_location","current_custodian","cb_state","current_customer","customer_branch","contact_person","delivery_date","expected_return_date","last_movement","last_movement_on"
 ],
 "fields": [
  {"fieldname":"reg_section","fieldtype":"Section Break","label":"Registration"},
  {"fieldname":"supplier","fieldtype":"Link","label":"Supplier","options":"Supplier","reqd":1,"in_list_view":1,"in_standard_filter":1},
  {"fieldname":"display_type","fieldtype":"Link","label":"Display Type","options":"Display Type","reqd":1,"in_list_view":1,"in_standard_filter":1},
  {"fieldname":"brand","fieldtype":"Link","label":"Brand","options":"Brand"},
  {"fieldname":"description","fieldtype":"Small Text","label":"Description"},
  {"fieldname":"size_model","fieldtype":"Data","label":"Size / Model"},
  {"fieldname":"cb_reg","fieldtype":"Column Break"},
  {"fieldname":"photo","fieldtype":"Attach Image","label":"Photo"},
  {"fieldname":"barcode","fieldtype":"Data","label":"Barcode / QR","read_only":1},
  {"fieldname":"remarks","fieldtype":"Small Text","label":"Remarks"},
  {"fieldname":"is_active","fieldtype":"Check","label":"Active","default":"1"},
  {"fieldname":"state_section","fieldtype":"Section Break","label":"Current State (system-maintained)"},
  {"fieldname":"current_status","fieldtype":"Select","label":"Current Status","read_only":1,"in_list_view":1,"in_standard_filter":1,"options":"At Supplier\nIn Warehouse\nReserved\nIn Transit\nInstalled at Customer\nReturned\nDamaged\nMissing\nUnder Repair\nReturned to Supplier"},
  {"fieldname":"current_location_type","fieldtype":"Select","label":"Location Type","read_only":1,"in_standard_filter":1,"options":"Warehouse\nCustomer\nDealer\nRetail Outlet\nService Center\nSupplier"},
  {"fieldname":"current_location","fieldtype":"Dynamic Link","label":"Current Location","options":"current_location_doctype","read_only":1},
  {"fieldname":"current_location_doctype","fieldtype":"Data","label":"Current Location DocType","hidden":1,"read_only":1},
  {"fieldname":"current_custodian","fieldtype":"Link","label":"Responsible (Custodian)","options":"Employee","read_only":1},
  {"fieldname":"cb_state","fieldtype":"Column Break"},
  {"fieldname":"current_customer","fieldtype":"Link","label":"Current Customer","options":"Customer","read_only":1},
  {"fieldname":"customer_branch","fieldtype":"Data","label":"Customer Branch","read_only":1},
  {"fieldname":"contact_person","fieldtype":"Data","label":"Contact Person","read_only":1},
  {"fieldname":"delivery_date","fieldtype":"Date","label":"Delivery Date","read_only":1},
  {"fieldname":"expected_return_date","fieldtype":"Date","label":"Expected Return Date","read_only":1,"in_standard_filter":1},
  {"fieldname":"last_movement","fieldtype":"Link","label":"Last Movement","options":"Display Movement","read_only":1},
  {"fieldname":"last_movement_on","fieldtype":"Datetime","label":"Last Movement On","read_only":1}
 ],
 "links": [
  {"link_doctype":"Display Movement","link_fieldname":"display_unit","group":"History"}
 ],
 "module": "Display Tracking", "name": "Display Unit", "owner": "Administrator",
 "permissions": [
  {"role":"System Manager","read":1,"write":1,"create":1,"delete":1,"report":1,"export":1},
  {"role":"Display Manager","read":1,"write":1,"create":1,"report":1,"export":1},
  {"role":"Warehouse User","read":1,"write":1,"create":1,"report":1},
  {"role":"Sales User","read":1,"report":1}
 ],
 "sort_field":"modified","sort_order":"DESC","track_changes":1
}
```

- [ ] **Step 4: Write the controller (defaults + barcode)**

`display_unit.py`:
```python
import frappe
from frappe.model.document import Document

LOCATION_DOCTYPE = {
    "Warehouse": "Warehouse Rack",
    "Customer": "Customer", "Dealer": "Customer", "Retail Outlet": "Customer",
    "Service Center": "Display Service Center",
    "Supplier": "Supplier",
}


class DisplayUnit(Document):
    def before_insert(self):
        if not self.current_status:
            self.current_status = "At Supplier"
            self.current_location_type = "Supplier"
            self.current_location = self.supplier
        self._sync_location_doctype()

    def after_insert(self):
        if self.barcode != self.name:
            frappe.db.set_value("Display Unit", self.name, "barcode", self.name,
                                update_modified=False)
            self.barcode = self.name

    def _sync_location_doctype(self):
        self.current_location_doctype = LOCATION_DOCTYPE.get(self.current_location_type)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `bench --site erp.chundakadan.in run-tests --module chundakadan.chundakadan.display_tracking.doctype.display_unit.test_display_unit`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add chundakadan/chundakadan/display_tracking/doctype/display_unit
git commit -m "feat(display): Display Unit master with cached current-state"
```

---

### Task 3: `Display Movement Photo` child + `Display Movement` DocType (schema only)

**Files:**
- Create: `chundakadan/chundakadan/display_tracking/doctype/display_movement_photo/display_movement_photo.json`
- Create: `.../display_movement_photo/display_movement_photo.py`, `__init__.py`
- Create: `chundakadan/chundakadan/display_tracking/doctype/display_movement/display_movement.json`
- Create: `.../display_movement/__init__.py`
- (controller `.py` added in Task 5)

**Interfaces:**
- Produces: submittable DocType `Display Movement` (fields per spec §3.4) + child `Display Movement Photo`. No controller logic yet.

- [ ] **Step 1: Create the child table JSON**

`display_movement_photo.json`:
```json
{
 "actions": [], "creation": "2026-07-10 00:00:00", "doctype": "DocType",
 "editable_grid": 1, "engine": "InnoDB", "istable": 1,
 "field_order": ["image","caption"],
 "fields": [
  {"fieldname":"image","fieldtype":"Attach Image","label":"Image","in_list_view":1},
  {"fieldname":"caption","fieldtype":"Data","label":"Caption","in_list_view":1}
 ],
 "links": [], "module": "Display Tracking", "name": "Display Movement Photo",
 "owner": "Administrator", "permissions": [], "sort_field":"modified","sort_order":"DESC"
}
```
`display_movement_photo.py`:
```python
from frappe.model.document import Document


class DisplayMovementPhoto(Document):
    pass
```

- [ ] **Step 2: Create the `Display Movement` JSON (submittable)**

`display_movement.json`:
```json
{
 "actions": [], "allow_rename": 0, "autoname": "DMV-.YYYY.-.######",
 "creation": "2026-07-10 00:00:00", "doctype": "DocType", "engine": "InnoDB",
 "is_submittable": 1,
 "field_order": [
  "display_unit","movement_type","movement_datetime","user",
  "from_section","from_status","from_location_type","from_location","from_location_doctype",
  "to_section","to_status","to_location_type","to_location","to_location_doctype","custodian",
  "cust_section","customer","customer_branch","contact_person","expected_return_date",
  "detail_section","reason","remarks","photos","signature","gps_section","latitude","longitude"
 ],
 "fields": [
  {"fieldname":"display_unit","fieldtype":"Link","label":"Display Unit","options":"Display Unit","reqd":1,"in_list_view":1,"search_index":1},
  {"fieldname":"movement_type","fieldtype":"Select","label":"Movement Type","reqd":1,"in_list_view":1,"options":"Receive at Warehouse\nReserve\nDispatch\nInstall at Customer\nTransfer\nReturn to Warehouse\nSend to Repair\nReturn from Repair\nMark Damaged\nMark Missing\nReturn to Supplier"},
  {"fieldname":"movement_datetime","fieldtype":"Datetime","label":"Date & Time","default":"now","reqd":1},
  {"fieldname":"user","fieldtype":"Link","label":"Logged By","options":"User","read_only":1},
  {"fieldname":"from_section","fieldtype":"Section Break","label":"From"},
  {"fieldname":"from_status","fieldtype":"Select","label":"From Status","read_only":1,"options":"\nAt Supplier\nIn Warehouse\nReserved\nIn Transit\nInstalled at Customer\nReturned\nDamaged\nMissing\nUnder Repair\nReturned to Supplier"},
  {"fieldname":"from_location_type","fieldtype":"Select","label":"From Location Type","read_only":1,"options":"\nWarehouse\nCustomer\nDealer\nRetail Outlet\nService Center\nSupplier"},
  {"fieldname":"from_location","fieldtype":"Dynamic Link","label":"From Location","options":"from_location_doctype","read_only":1},
  {"fieldname":"from_location_doctype","fieldtype":"Data","hidden":1,"read_only":1},
  {"fieldname":"to_section","fieldtype":"Section Break","label":"To"},
  {"fieldname":"to_status","fieldtype":"Select","label":"To Status","read_only":1,"options":"\nAt Supplier\nIn Warehouse\nReserved\nIn Transit\nInstalled at Customer\nReturned\nDamaged\nMissing\nUnder Repair\nReturned to Supplier"},
  {"fieldname":"to_location_type","fieldtype":"Select","label":"To Location Type","options":"\nWarehouse\nCustomer\nDealer\nRetail Outlet\nService Center\nSupplier"},
  {"fieldname":"to_location","fieldtype":"Dynamic Link","label":"To Location","options":"to_location_doctype"},
  {"fieldname":"to_location_doctype","fieldtype":"Data","hidden":1,"read_only":1},
  {"fieldname":"custodian","fieldtype":"Link","label":"Responsible (Custodian)","options":"Employee"},
  {"fieldname":"cust_section","fieldtype":"Section Break","label":"Customer"},
  {"fieldname":"customer","fieldtype":"Link","label":"Customer","options":"Customer"},
  {"fieldname":"customer_branch","fieldtype":"Data","label":"Branch"},
  {"fieldname":"contact_person","fieldtype":"Data","label":"Contact Person"},
  {"fieldname":"expected_return_date","fieldtype":"Date","label":"Expected Return Date"},
  {"fieldname":"detail_section","fieldtype":"Section Break","label":"Detail & Evidence"},
  {"fieldname":"reason","fieldtype":"Small Text","label":"Reason"},
  {"fieldname":"remarks","fieldtype":"Small Text","label":"Remarks"},
  {"fieldname":"photos","fieldtype":"Table","label":"Photos","options":"Display Movement Photo"},
  {"fieldname":"signature","fieldtype":"Attach Image","label":"Signature"},
  {"fieldname":"gps_section","fieldtype":"Section Break","label":"GPS"},
  {"fieldname":"latitude","fieldtype":"Float","label":"Latitude","precision":"6"},
  {"fieldname":"longitude","fieldtype":"Float","label":"Longitude","precision":"6"}
 ],
 "links": [], "module": "Display Tracking", "name": "Display Movement", "owner": "Administrator",
 "permissions": [
  {"role":"System Manager","read":1,"write":1,"create":1,"submit":1,"cancel":1,"report":1,"export":1},
  {"role":"Display Manager","read":1,"write":1,"create":1,"submit":1,"cancel":1,"report":1,"export":1},
  {"role":"Warehouse User","read":1,"write":1,"create":1,"submit":1},
  {"role":"Sales User","read":1,"write":1,"create":1,"submit":1}
 ],
 "sort_field":"modified","sort_order":"DESC"
}
```
Note: **no `delete` permission on any role** — satisfies the never-delete constraint. `cancel` only on System Manager + Display Manager.

- [ ] **Step 3: Migrate and verify both DocTypes exist**

Run: `cd ~/frappe-bench-15-india && bench --site erp.chundakadan.in migrate`
Expected: completes; `Display Movement` (submittable) + `Display Movement Photo` created.

- [ ] **Step 4: Commit**

```bash
git add chundakadan/chundakadan/display_tracking/doctype/display_movement chundakadan/chundakadan/display_tracking/doctype/display_movement_photo
git commit -m "feat(display): Display Movement submittable ledger schema + photo child"
```

---

### Task 4: Transition map (pure module, TDD)

**Files:**
- Create: `chundakadan/chundakadan/display_tracking/transitions.py`
- Create: `chundakadan/chundakadan/display_tracking/test_transitions.py`

**Interfaces:**
- Produces:
  - `TRANSITIONS: dict[str, dict]` keyed by movement_type → `{"to_status": str, "to_location_type": str|None, "allowed_from": set[str], "requires": list[str]}`.
  - `resolve_transition(movement_type: str, from_status: str) -> dict` — returns the transition dict or raises `frappe.ValidationError` (via `frappe.throw`) if the move is illegal.
  - `LOCATION_DOCTYPE: dict[str,str]` (location_type → DocType name).
- Consumes: nothing (pure; imports `frappe` only for `_` and `throw`).

- [ ] **Step 1: Write the failing tests**

`test_transitions.py`:
```python
import unittest
import frappe
from chundakadan.chundakadan.display_tracking.transitions import (
    resolve_transition, TRANSITIONS, LOCATION_DOCTYPE,
)


class TestTransitions(unittest.TestCase):
    def test_receive_from_at_supplier(self):
        t = resolve_transition("Receive at Warehouse", "At Supplier")
        self.assertEqual(t["to_status"], "In Warehouse")
        self.assertEqual(t["to_location_type"], "Warehouse")

    def test_install_sets_installed(self):
        t = resolve_transition("Install at Customer", "In Warehouse")
        self.assertEqual(t["to_status"], "Installed at Customer")
        self.assertIn("customer", t["requires"])
        self.assertIn("expected_return_date", t["requires"])

    def test_return_to_warehouse_sets_returned(self):
        t = resolve_transition("Return to Warehouse", "Installed at Customer")
        self.assertEqual(t["to_status"], "Returned")

    def test_dispatch_leaves_location_unchanged(self):
        t = resolve_transition("Dispatch", "In Warehouse")
        self.assertEqual(t["to_status"], "In Transit")
        self.assertIsNone(t["to_location_type"])

    def test_illegal_transition_raises(self):
        with self.assertRaises(frappe.ValidationError):
            resolve_transition("Reserve", "Installed at Customer")

    def test_location_doctype_map(self):
        self.assertEqual(LOCATION_DOCTYPE["Warehouse"], "Warehouse Rack")
        self.assertEqual(LOCATION_DOCTYPE["Dealer"], "Customer")
        self.assertEqual(LOCATION_DOCTYPE["Service Center"], "Display Service Center")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/frappe-bench-15-india && bench --site erp.chundakadan.in run-tests --module chundakadan.chundakadan.display_tracking.test_transitions`
Expected: FAIL — `transitions` module not found.

- [ ] **Step 3: Implement `transitions.py`**

```python
import frappe
from frappe import _

LOCATION_DOCTYPE = {
    "Warehouse": "Warehouse Rack",
    "Customer": "Customer", "Dealer": "Customer", "Retail Outlet": "Customer",
    "Service Center": "Display Service Center",
    "Supplier": "Supplier",
}

# to_location_type = None  → leave the unit's location unchanged
TRANSITIONS = {
    "Receive at Warehouse": {"to_status": "In Warehouse", "to_location_type": "Warehouse",
        "allowed_from": {"At Supplier", "In Transit", "Under Repair"}, "requires": ["to_location"]},
    "Reserve": {"to_status": "Reserved", "to_location_type": "Warehouse",
        "allowed_from": {"In Warehouse", "Returned"}, "requires": []},
    "Dispatch": {"to_status": "In Transit", "to_location_type": None,
        "allowed_from": {"In Warehouse", "Reserved", "Returned"}, "requires": []},
    "Install at Customer": {"to_status": "Installed at Customer", "to_location_type": "Customer",
        "allowed_from": {"In Transit", "In Warehouse", "Reserved", "Returned"},
        "requires": ["customer", "expected_return_date"]},
    "Transfer": {"to_status": "Installed at Customer", "to_location_type": "Customer",
        "allowed_from": {"Installed at Customer"},
        "requires": ["customer", "expected_return_date"]},
    "Return to Warehouse": {"to_status": "Returned", "to_location_type": "Warehouse",
        "allowed_from": {"Installed at Customer", "In Transit", "Under Repair"}, "requires": ["to_location"]},
    "Send to Repair": {"to_status": "Under Repair", "to_location_type": "Service Center",
        "allowed_from": {"In Warehouse", "Returned", "Installed at Customer", "Damaged"},
        "requires": ["to_location"]},
    "Return from Repair": {"to_status": "In Warehouse", "to_location_type": "Warehouse",
        "allowed_from": {"Under Repair"}, "requires": ["to_location"]},
    "Mark Damaged": {"to_status": "Damaged", "to_location_type": None,
        "allowed_from": None, "requires": ["reason"]},   # None = any status
    "Mark Missing": {"to_status": "Missing", "to_location_type": None,
        "allowed_from": None, "requires": ["reason"]},
    "Return to Supplier": {"to_status": "Returned to Supplier", "to_location_type": "Supplier",
        "allowed_from": {"In Warehouse", "Returned", "Damaged", "Missing", "Under Repair"}, "requires": []},
}


def resolve_transition(movement_type, from_status):
    t = TRANSITIONS.get(movement_type)
    if not t:
        frappe.throw(_("Unknown movement type: {0}").format(movement_type))
    allowed = t["allowed_from"]
    if allowed is not None and from_status not in allowed:
        frappe.throw(_("Cannot '{0}' a unit that is '{1}'. Allowed only from: {2}.").format(
            movement_type, from_status, ", ".join(sorted(allowed))))
    return t
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bench --site erp.chundakadan.in run-tests --module chundakadan.chundakadan.display_tracking.test_transitions`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add chundakadan/chundakadan/display_tracking/transitions.py chundakadan/chundakadan/display_tracking/test_transitions.py
git commit -m "feat(display): transition map with validation (TDD)"
```

---

### Task 5: `Display Movement` controller (validate / on_submit / on_cancel)

**Files:**
- Create: `chundakadan/chundakadan/display_tracking/doctype/display_movement/display_movement.py`
- Create: `chundakadan/chundakadan/display_tracking/doctype/display_movement/test_display_movement.py`

**Interfaces:**
- Consumes: `resolve_transition`, `LOCATION_DOCTYPE` (Task 4); `Display Unit` (Task 2); `Display Movement` schema (Task 3).
- Produces: the `DisplayMovement` controller. `on_submit` writes cached state onto the unit; `on_cancel` (Display Manager only) recomputes the unit from the latest remaining submitted movement.

- [ ] **Step 1: Write the failing tests**

`test_display_movement.py`:
```python
import frappe
from frappe.tests.utils import FrappeTestCase


class TestDisplayMovement(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not frappe.db.exists("Display Type", "Rack"):
            frappe.get_doc({"doctype": "Display Type", "type_name": "Rack"}).insert()
        if not frappe.db.exists("Supplier", "_Test Display Supplier"):
            frappe.get_doc({"doctype": "Supplier", "supplier_name": "_Test Display Supplier",
                "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")}).insert()
        if not frappe.db.exists("Customer", "_Test Display Customer"):
            frappe.get_doc({"doctype": "Customer", "customer_name": "_Test Display Customer",
                "customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
                "territory": frappe.db.get_value("Territory", {"is_group": 0}, "name")}).insert()

    def _unit(self):
        return frappe.get_doc({"doctype": "Display Unit", "supplier": "_Test Display Supplier",
                               "display_type": "Rack"}).insert()

    def _move(self, unit, mtype, **kw):
        m = frappe.get_doc({"doctype": "Display Movement", "display_unit": unit.name,
                            "movement_type": mtype, **kw})
        m.insert()
        m.submit()
        return m

    def test_receive_updates_unit(self):
        u = self._unit()
        self._move(u, "Receive at Warehouse", to_location_type="Warehouse")
        u.reload()
        self.assertEqual(u.current_status, "In Warehouse")
        self.assertEqual(u.current_location_type, "Warehouse")

    def test_install_requires_customer(self):
        u = self._unit()
        self._move(u, "Receive at Warehouse", to_location_type="Warehouse")
        with self.assertRaises(frappe.ValidationError):
            self._move(u, "Install at Customer")  # missing customer + expected_return_date

    def test_full_install_flow(self):
        u = self._unit()
        self._move(u, "Receive at Warehouse", to_location_type="Warehouse")
        self._move(u, "Install at Customer", customer="_Test Display Customer",
                   expected_return_date="2027-01-01", to_location_type="Customer",
                   to_location="_Test Display Customer")
        u.reload()
        self.assertEqual(u.current_status, "Installed at Customer")
        self.assertEqual(u.current_customer, "_Test Display Customer")
        self.assertEqual(str(u.expected_return_date), "2027-01-01")

    def test_illegal_move_blocked(self):
        u = self._unit()  # At Supplier
        with self.assertRaises(frappe.ValidationError):
            self._move(u, "Reserve")  # not allowed from At Supplier

    def test_cancel_recomputes_previous_state(self):
        u = self._unit()
        self._move(u, "Receive at Warehouse", to_location_type="Warehouse")
        m2 = self._move(u, "Reserve")
        u.reload(); self.assertEqual(u.current_status, "Reserved")
        m2.cancel()
        u.reload()
        self.assertEqual(u.current_status, "In Warehouse")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bench --site erp.chundakadan.in run-tests --module chundakadan.chundakadan.display_tracking.doctype.display_movement.test_display_movement`
Expected: FAIL — controller not implemented (state not updated / no validation).

- [ ] **Step 3: Implement the controller**

`display_movement.py`:
```python
import frappe
from frappe import _
from frappe.model.document import Document
from chundakadan.chundakadan.display_tracking.transitions import (
    resolve_transition, LOCATION_DOCTYPE,
)

# Fields copied from a movement onto the Display Unit cache on submit.
_CACHE_FIELDS = [
    "current_status", "current_location_type", "current_location",
    "current_custodian", "current_customer", "customer_branch",
    "contact_person", "expected_return_date",
]


class DisplayMovement(Document):
    def validate(self):
        unit = frappe.get_doc("Display Unit", self.display_unit)
        # snapshot the "from" side from the unit's current cache
        self.from_status = unit.current_status
        self.from_location_type = unit.current_location_type
        self.from_location = unit.current_location
        self.from_location_doctype = LOCATION_DOCTYPE.get(unit.current_location_type)
        if not self.user:
            self.user = frappe.session.user

        t = resolve_transition(self.movement_type, unit.current_status)
        self.to_status = t["to_status"]
        # location: None means "unchanged"; else default to the transition's type
        if t["to_location_type"] is None:
            self.to_location_type = unit.current_location_type
            if not self.to_location:
                self.to_location = unit.current_location
        elif not self.to_location_type:
            self.to_location_type = t["to_location_type"]
        self.to_location_doctype = LOCATION_DOCTYPE.get(self.to_location_type)

        for f in t["requires"]:
            if not self.get(f):
                frappe.throw(_("'{0}' is required for movement '{1}'.").format(
                    self.meta.get_label(f), self.movement_type))

    def on_submit(self):
        self._write_unit_state()

    def on_cancel(self):
        if "Display Manager" not in frappe.get_roles(frappe.session.user):
            frappe.throw(_("Only a Display Manager may cancel a movement. "
                           "Log a reversing movement instead."))
        self._recompute_unit_from_history()

    # -- helpers ---------------------------------------------------------
    def _write_unit_state(self):
        vals = {
            "current_status": self.to_status,
            "current_location_type": self.to_location_type,
            "current_location": self.to_location,
            "current_location_doctype": LOCATION_DOCTYPE.get(self.to_location_type),
            "current_custodian": self.custodian,
            "current_customer": self.customer,
            "customer_branch": self.customer_branch,
            "contact_person": self.contact_person,
            "expected_return_date": self.expected_return_date,
            "last_movement": self.name,
            "last_movement_on": self.movement_datetime,
        }
        if self.movement_type in ("Install at Customer", "Transfer"):
            vals["delivery_date"] = frappe.utils.getdate(self.movement_datetime)
        frappe.db.set_value("Display Unit", self.display_unit, vals)

    def _recompute_unit_from_history(self):
        prev = frappe.get_all("Display Movement",
            filters={"display_unit": self.display_unit, "docstatus": 1,
                     "name": ["!=", self.name]},
            order_by="movement_datetime desc, creation desc", limit=1, pluck="name")
        if prev:
            frappe.get_doc("Display Movement", prev[0])._write_unit_state()
        else:
            # back to registration baseline
            supplier = frappe.db.get_value("Display Unit", self.display_unit, "supplier")
            frappe.db.set_value("Display Unit", self.display_unit, {
                "current_status": "At Supplier", "current_location_type": "Supplier",
                "current_location": supplier, "current_location_doctype": "Supplier",
                "current_custodian": None, "current_customer": None,
                "customer_branch": None, "contact_person": None,
                "expected_return_date": None, "last_movement": None, "last_movement_on": None,
            })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bench --site erp.chundakadan.in run-tests --module chundakadan.chundakadan.display_tracking.doctype.display_movement.test_display_movement`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add chundakadan/chundakadan/display_tracking/doctype/display_movement/display_movement.py chundakadan/chundakadan/display_tracking/doctype/display_movement/test_display_movement.py
git commit -m "feat(display): Display Movement controller — validate/on_submit/on_cancel (TDD)"
```

---

### Task 6: "Display View" workspace + Number Cards + Dashboard Charts

**Files:**
- Create (via desk in developer mode, then export): Number Card records ×7, Dashboard Chart records ×4, Workspace `Display View`.
- Modify: `chundakadan/chundakadan/hooks.py` (fixtures list — Task 8 finalizes export).

**Interfaces:**
- Produces: a public Workspace `Display View` (`sequence_id=3`) showing the cards, shortcuts, and charts. All reference `Display Unit`/`Display Movement`.

- [ ] **Step 1: Create the 7 Number Cards**

In the desk (developer mode on), **New Number Card** for each row — Document Type = `Display Unit` (Report/Count), function `Count`, filters as below; label exactly as given:

| Label | Document Type | Filters (JSON) |
|---|---|---|
| Total Display Units | Display Unit | `[["is_active","=",1]]` |
| In Warehouse | Display Unit | `[["current_location_type","=","Warehouse"]]` |
| At Customer | Display Unit | `[["current_location_type","in",["Customer","Dealer","Retail Outlet"]]]` |
| In Transit | Display Unit | `[["current_status","=","In Transit"]]` |
| Damaged | Display Unit | `[["current_status","=","Damaged"]]` |
| Missing | Display Unit | `[["current_status","=","Missing"]]` |
| Due for Return | Display Unit | `[["current_status","=","Installed at Customer"],["expected_return_date","<=","Today"]]` |

For "Due for Return", set the filter value to the dynamic string `Today` (Frappe resolves it at render). If the UI rejects the compound filter, create it as a **Report** Number Card backed by a saved report with the same filter.

- [ ] **Step 2: Create the 4 Dashboard Charts**

**New Dashboard Chart** for each (Type = Group By / Count, Document Type as given):

| Chart Name | Document Type | Group By Field | Type |
|---|---|---|---|
| Display Units by Status | Display Unit | current_status | Donut |
| Display Units by Location Type | Display Unit | current_location_type | Bar |
| Display Units by Supplier | Display Unit | supplier | Bar |
| Display Movements per Month | Display Movement | movement_datetime (Count, Monthly) | Line |

- [ ] **Step 3: Create the Workspace**

**New Workspace**: Title `Display View`, Module `Display Tracking`, Public ✓, **sequence_id `3`**. Add:
- **Shortcuts** → Display Unit, Display Movement, Display Type, and a Display Unit shortcut named "Due for Return" with `stats_filter` `{"current_status":"Installed at Customer","expected_return_date":["<=","Today"]}`.
- **Number Cards** → the 7 from Step 1.
- **Charts** → the 4 from Step 2.

- [ ] **Step 4: Verify on the desk**

Reload; open the `Display View` workspace. Confirm it appears at sidebar position 3, all cards render numbers, charts render.

- [ ] **Step 5: Commit is deferred to Task 8** (these become fixtures there so they migrate to other sites).

---

### Task 7: Seed masters + list-view polish

**Files:**
- Create: `chundakadan/chundakadan/display_tracking/doctype/display_type/display_type.json` list settings (already in Task 1) — add seed via a data patch.
- Create: `chundakadan/patches/v1_0/seed_display_types.py`
- Modify: `chundakadan/patches.txt`

**Interfaces:**
- Produces: the six standard Display Types seeded idempotently on migrate.

- [ ] **Step 1: Write the seed patch**

`chundakadan/patches/v1_0/seed_display_types.py`:
```python
import frappe

TYPES = ["Display Rack", "Display Shelf", "Display Stand", "Cooler",
         "Branding Material", "Promotional Display"]


def execute():
    for t in TYPES:
        if not frappe.db.exists("Display Type", t):
            frappe.get_doc({"doctype": "Display Type", "type_name": t}).insert(ignore_permissions=True)
```

- [ ] **Step 2: Register the patch**

Append to `chundakadan/patches.txt`:
```
chundakadan.patches.v1_0.seed_display_types
```

- [ ] **Step 3: Run migrate + verify**

Run: `cd ~/frappe-bench-15-india && bench --site erp.chundakadan.in migrate`
Expected: 6 Display Types exist:
```bash
bench --site erp.chundakadan.in execute frappe.db.count --kwargs '{"dt":"Display Type"}'
```

- [ ] **Step 4: Commit**

```bash
git add chundakadan/patches/v1_0/seed_display_types.py chundakadan/patches.txt
git commit -m "feat(display): seed standard display types on migrate"
```

---

### Task 8: Fixtures export, roles & final verification

**Files:**
- Modify: `chundakadan/chundakadan/hooks.py` (add `fixtures`)
- Create: exported fixture JSONs under `chundakadan/fixtures/`

**Interfaces:**
- Produces: reproducible fixtures so the whole feature (workspace, cards, charts, naming rules, roles, customer groups) installs on any site via migrate.

- [ ] **Step 1: Add Document Naming Rules (desk) for both DocTypes**

Create **Document Naming Rule** records: `Display Unit` → `DISP-.YYYY.-.#####`; `Display Movement` → `DMV-.YYYY.-.######`. (The DocType `autoname` already matches, so this is belt-and-suspenders + matches the project's naming-rule convention from commit 69a9605.)

- [ ] **Step 2: Add the fixtures block to hooks.py**

In `chundakadan/chundakadan/hooks.py`, add (or extend an existing `fixtures = [...]`):
```python
fixtures = [
    {"dt": "Workspace", "filters": [["name", "=", "Display View"]]},
    {"dt": "Number Card", "filters": [["module", "=", "Display Tracking"]]},
    {"dt": "Dashboard Chart", "filters": [["module", "=", "Display Tracking"]]},
    {"dt": "Document Naming Rule", "filters": [["document_type", "in", ["Display Unit", "Display Movement"]]]},
    {"dt": "Role", "filters": [["name", "in", ["Display Manager", "Warehouse User"]]]},
    {"dt": "Customer Group", "filters": [["name", "in", ["Dealer", "Retail Outlet"]]]},
]
```
(If `fixtures` already exists, merge these entries in.)

- [ ] **Step 3: Export fixtures**

Run:
```bash
cd ~/frappe-bench-15-india && bench --site erp.chundakadan.in export-fixtures --app chundakadan
```
Expected: JSON files written under `chundakadan/fixtures/` for the above.

- [ ] **Step 4: Full clean verification (migrate + all tests)**

```bash
cd ~/frappe-bench-15-india
bench --site erp.chundakadan.in migrate
bench --site erp.chundakadan.in run-tests --module chundakadan.chundakadan.display_tracking.test_transitions
bench --site erp.chundakadan.in run-tests --module chundakadan.chundakadan.display_tracking.doctype.display_unit.test_display_unit
bench --site erp.chundakadan.in run-tests --module chundakadan.chundakadan.display_tracking.doctype.display_movement.test_display_movement
```
Expected: migrate clean; all three test modules PASS.

- [ ] **Step 5: Manual smoke test (desk)**

Create a Display Unit → confirm `At Supplier`. Log Receive at Warehouse (submit) → unit shows In Warehouse. Log Install at Customer with a customer + expected return (submit) → unit shows Installed at Customer, custodian/customer set. Open Display View → cards + charts reflect it. Try to delete a submitted Display Movement → blocked.

- [ ] **Step 6: Commit + push upstream**

```bash
cd ~/frappe-bench-15-india/apps/chundakadan
git add chundakadan/chundakadan/hooks.py chundakadan/fixtures
git commit -m "feat(display): export workspace/cards/charts/naming/roles fixtures; Phase 1 complete"
git push upstream main   # (requires the maintainer's push creds)
```

---

## Self-Review Notes

- **Spec coverage:** registration (Task 2), custody/Employee (Tasks 2/5), location Dynamic Link (Tasks 2/3/5), status + transitions (Task 4), submittable immutable ledger + no-delete (Task 3 perms), on_submit cache write (Task 5), manager-only cancel + recompute (Task 5), reused masters + Customer Groups (Task 1), naming rules (Tasks 2/3/8), workspace + 7 cards + 4 charts + shortcuts (Task 6), roles/permissions (Tasks 1/3/6), seeds (Task 7), fixtures (Task 8). ✔
- **Deferred (non-goals, not in this plan):** QR label print format, Flutter mobile flows, utilisation report, return-due scheduler.
- **Type consistency:** `resolve_transition`, `LOCATION_DOCTYPE`, `_write_unit_state`, `current_location_doctype`/`from_location_doctype`/`to_location_doctype` companion fields used consistently across Tasks 2–5.
