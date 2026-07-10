# Display Tracking System — Phase 1 (Desk Core Ledger) — Design Spec

- **Date:** 2026-07-10
- **App:** `chundakadan` (new module: **Display Tracking**)
- **Status:** Approved for implementation planning
- **Scope:** Phase 1 — desk core ledger **plus the "Display View" workspace** (Number Cards + Shortcuts + Dashboard charts). QR/label printing, the Flutter mobile flows, the utilisation report, and the return-due scheduler remain later phases (out of scope here).

## 1. Problem

Suppliers lend Chundakadan display units (racks, shelves, stands, coolers, branding, promotional displays). They are **not** inventory, assets, or purchase/sales documents and have **zero** financial/GL/stock impact. We must always know, per unit: where it is, who is responsible, when received/delivered, when it must return, and its complete, immutable movement history. Must scale to tens of thousands of units.

## 2. Architecture — custody ledger

Mirror ERPNext's stock pattern (immutable Stock Ledger Entry + cached Bin), minus the money:

- **`Display Unit`** — master, one per physical unit. Holds registration data **plus a cached snapshot** of current state (status/location/custodian/customer/dates). All dashboards and lookups read this cache → fast at scale.
- **`Display Movement`** — append-only ledger, one record per event. Submittable; once submitted it is locked. This **is** the movement history and audit trail. On submit it writes the new state onto the Unit.

The Unit's current-state fields are **never edited by hand** — only the movement controller writes them. History lives only in movements (no child-table history on the Unit).

## 3. DocTypes

### 3.1 `Display Type` (master)
Small controlled list of display categories.

| Field | Type | Notes |
|---|---|---|
| type_name | Data | unique; naming = `field:type_name` |
| description | Small Text | |
| disabled | Check | |

Seed values: Display Rack, Display Shelf, Display Stand, Cooler, Branding Material, Promotional Display.

### 3.2 `Display Service Center` (master)
Small list of repair locations (few records).

| Field | Type | Notes |
|---|---|---|
| service_center_name | Data | naming = `field:service_center_name` |
| address | Small Text | |
| disabled | Check | |

### 3.3 `Display Unit` (master — NOT submittable)
Naming: Document Naming Rule `DISP-.YYYY.-.#####`. `barcode` mirrors `name`.

**Registration (user-editable):**

| Field | Type | Notes |
|---|---|---|
| supplier | Link → Supplier | reqd |
| display_type | Link → Display Type | reqd |
| brand | Link → Brand | |
| description | Small Text | |
| size_model | Data | |
| photo | Attach Image | |
| barcode | Data | read-only; = `name`, set on autoname |
| remarks | Small Text | |
| is_active | Check | default 1 |

**Current state (read-only in UI; written only by the movement controller):**

| Field | Type | Notes |
|---|---|---|
| current_status | Select | the 10 statuses (§4). Default `At Supplier` on create |
| current_location_type | Select | Warehouse, Customer, Dealer, Retail Outlet, Service Center, Supplier |
| current_location | Dynamic Link | options field = `current_location_type_link_doctype` (see §5 mapping) |
| current_custodian | Link → Employee | |
| current_customer | Link → Customer | set when at a customer-side location |
| customer_branch | Data | free text (or Link → Address later) |
| contact_person | Data | |
| delivery_date | Date | last install date |
| expected_return_date | Date | |
| last_movement | Link → Display Movement | |
| last_movement_on | Datetime | |

### 3.4 `Display Movement` (ledger — SUBMITTABLE)
Naming: Document Naming Rule `DMV-.YYYY.-.######`.

| Field | Type | Notes |
|---|---|---|
| display_unit | Link → Display Unit | reqd; **indexed** |
| movement_type | Select | §4 list; reqd |
| movement_datetime | Datetime | default now |
| user | Link → User | default session user; read-only |
| from_status | Select | auto-filled from unit at validate; read-only |
| from_location_type | Select | auto-filled; read-only |
| from_location | Dynamic Link | auto-filled; read-only |
| to_status | Select | computed from transition; read-only |
| to_location_type | Select | computed / user-picked per type |
| to_location | Dynamic Link | user-picked (e.g. target Rack / Customer / Service Center) |
| custodian | Link → Employee | new responsible party |
| customer | Link → Customer | required for Install/Transfer |
| customer_branch | Data | |
| contact_person | Data | |
| expected_return_date | Date | required for Install/Transfer |
| reason | Small Text | |
| remarks | Small Text | |
| photos | Table → Display Movement Photo | optional supporting photos |
| signature | Attach Image | used by mobile later; optional now |
| latitude | Float | GPS; optional now (mobile later) |
| longitude | Float | GPS; optional now |

### 3.5 `Display Movement Photo` (child table)
| Field | Type |
|---|---|
| image | Attach Image |
| caption | Data |

## 4. Status & transition model

**Statuses (10):** At Supplier, In Warehouse, Reserved, In Transit, Installed at Customer, Returned, Damaged, Missing, Under Repair, Returned to Supplier.

**Registration is the unit's creation event** — creating a `Display Unit` sets `current_status = At Supplier` and `current_location_type = Supplier` directly. There is **no** "Register" movement; the ledger begins with the first physical move (usually *Receive at Warehouse*). The creation record (owner + creation timestamp on the Unit) is the registration audit.

Two warehouse-present statuses are kept distinct on purpose: **In Warehouse** = received from supplier, never deployed; **Returned** = came back from a customer/repair. Both are physically in the warehouse (`current_location_type = Warehouse`).

**Transition map** (`movement_type` → resulting `to_status` / `to_location_type`; required fields):

| movement_type | to_status | to_location_type | Requires | Allowed from status |
|---|---|---|---|---|
| Receive at Warehouse | In Warehouse | Warehouse | to_location (Rack) | At Supplier, In Transit, Under Repair |
| Reserve | Reserved | Warehouse | — | In Warehouse, Returned |
| Dispatch | In Transit | *unchanged (still last location until arrival)* | — | In Warehouse, Reserved, Returned |
| Install at Customer | Installed at Customer | Customer / Dealer / Retail Outlet | customer, expected_return_date | In Transit, In Warehouse, Reserved, Returned |
| Transfer | Installed at Customer | Customer / Dealer / Retail Outlet | customer (new), expected_return_date | Installed at Customer |
| Return to Warehouse | **Returned** | Warehouse | to_location (Rack) | Installed at Customer, In Transit, Under Repair |
| Send to Repair | Under Repair | Service Center | to_location (Service Center) | In Warehouse, Returned, Installed at Customer, Damaged |
| Return from Repair | In Warehouse | Warehouse | to_location (Rack) | Under Repair |
| Mark Damaged | Damaged | (unchanged) | reason | any status |
| Mark Missing | Missing | (unchanged) | reason | any status |
| Return to Supplier | Returned to Supplier | Supplier | — | In Warehouse, Returned, Damaged, Missing, Under Repair |

Illegal transitions (movement_type not allowed from the unit's current status) are **rejected in `validate`** with a clear message. `Dispatch` sets status = In Transit but leaves `current_location*` at the last known physical location until an *Install* or *Receive* confirms arrival.

## 5. `current_location_type` → Dynamic Link target

| location_type | links to |
|---|---|
| Warehouse | Warehouse Rack |
| Customer / Dealer / Retail Outlet | Customer (Dealer/Retail Outlet distinguished by Customer Group) |
| Service Center | Display Service Center |
| Supplier | Supplier |

Implementation: a hidden companion field resolves the type to the DocType name for the Dynamic Link `options`.

## 6. Controller behaviour (`Display Movement`)

- **validate:** load the linked unit; fill `from_status/from_location_type/from_location` from the unit's cache; look up the transition for `movement_type`; if the current status isn't in *Allowed from*, `frappe.throw`; set `to_status` and default `to_location_type`; enforce required fields for that movement_type.
- **on_submit:** write onto the Display Unit (via `frappe.db.set_value`, `update_modified=True`): `current_status`, `current_location_type`, `current_location`, `current_custodian`, `current_customer`, `customer_branch`, `contact_person`, `delivery_date` (for Install/Transfer), `expected_return_date`, `last_movement`, `last_movement_on`.
- **on_cancel:** permitted only for role `Display Manager`. On cancel, recompute the unit's current state from the **latest remaining submitted** Display Movement (or reset to the Register baseline if none). Nothing is deleted — the cancelled movement (docstatus 2) stays as a record.
- Movements are never deleted: delete permission granted to no role.

## 7. Reused masters & prerequisites

- **Supplier, Customer, Brand, Employee** — existing ERPNext masters, linked (not duplicated).
- **Warehouse Rack / Warehouse Row** — existing chundakadan masters for warehouse sub-location.
- **Customer Group** values `Dealer`, `Retail Outlet` — ensure they exist (used to distinguish customer-side location types).

## 8. Roles & permissions

| Role | Display Unit | Display Movement |
|---|---|---|
| Display Manager | create/read/write | create/submit/**cancel**; read/write |
| Warehouse User | create/read/write | create/submit (warehouse-side types); read |
| Field Rep (Sales User) | read | create/submit (Install/Transfer/Return); read |
| — (everyone) | no delete | **no delete** |

## 9. Naming

Use **Document Naming Rule** records (consistent with commit 69a9605's move away from code hooks): `DISP-.YYYY.-.#####` for Display Unit, `DMV-.YYYY.-.######` for Display Movement.

## 10. Workspace — "Display View"

A public Workspace in the **Display Tracking** module.

- **label / name:** `Display View`
- **sequence_id:** `3` (sidebar order)
- **module:** Display Tracking
- **public:** 1

**Number Cards** (all read the cached `Display Unit` fields → single indexed count each):

| Card | Filter |
|---|---|
| Total Display Units | `is_active = 1` |
| In Warehouse | `current_location_type = Warehouse` (covers In Warehouse + Returned + Reserved) |
| At Customer | `current_location_type IN (Customer, Dealer, Retail Outlet)` |
| In Transit | `current_status = In Transit` |
| Damaged | `current_status = Damaged` |
| Missing | `current_status = Missing` |
| Due for Return | `current_status = Installed at Customer` AND `expected_return_date <= Today` |

"In Warehouse" and "At Customer" cards are **place-based** (`current_location_type`) so they count everything physically there regardless of the finer status; the rest are condition-based (`current_status`).

(The "Due for Return" card uses a dynamic `Today` filter; if the Number Card UI can't express the compound filter, back it with a small Report-type card.)

**Shortcuts:** Display Unit, Display Movement, Display Type, and a filtered "Due for Return" shortcut (Display Unit filtered as above).

**Dashboard charts** (Group By on cached fields, so they stay fast):

| Chart | Source |
|---|---|
| Units by Status | `Display Unit` group by `current_status` (donut) |
| Units by Location Type | `Display Unit` group by `current_location_type` (bar) |
| Units by Supplier | `Display Unit` group by `supplier` (bar, top N) |
| Movements per Month | `Display Movement` count by month (line) |

All workspace elements (Number Card, Dashboard Chart, Workspace) ship as fixtures in the app so they migrate with the code.

## 11. Non-goals (Phase 1)

Deferred to later phases: QR/barcode label print format & scanning; the Flutter mobile flows (scan / check-in-out / signature / GPS capture); the Display Utilisation report (days-at-customer vs idle); and the return-due scheduler + push notifications. The `signature`/`latitude`/`longitude` fields are created now but only populated once mobile lands.

## 12. Testing focus

- Transition validity: each `movement_type` accepted only from its *Allowed from* statuses; illegal ones throw.
- On-submit write-back sets every cached field correctly; a fresh unit starts `At Supplier`.
- Immutability: a submitted movement can't be edited; delete is denied for all roles.
- Cancel recompute: cancelling the latest movement restores the unit to the prior movement's state; cancelling a non-latest movement is handled (block, or recompute from latest remaining).
- Required-field enforcement per movement_type (Install/Transfer need customer + expected_return_date).
