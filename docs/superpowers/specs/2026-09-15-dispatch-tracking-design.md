# Dispatch Tracking — Design

Date: 2026-09-15
App: `chundakadan` (ERPNext v15, India Compliance). Production runs on Frappe Cloud; code ships through this repo.

## Goal

A dispatch staff member (new role **Dispatch User**) tracks every Sales Invoice of **Chundakadan Agencies** from billing to delivery:

1. Mark whether the goods are dispatched, and if so by which transport partner, vehicle and LR.
2. For invoices not yet dispatched, record why.
3. For dispatched invoices, follow up on the expected delivery date by calling the customer, and record Delivered or Not Delivered.

Only the dispatcher knows transport details. The accountant does **not** fill Transporter Info when creating the invoice, and invoice submit is **not** blocked on transport details. The dispatcher fills them afterwards from the Dispatch page.

## Scope

In scope: Sales Invoices of company `Chundakadan Agencies`, `docstatus = 1`, `is_return = 0`, `is_opening != "Yes"`.
Out of scope: Chundakadan Home Stop, returns/credit notes, opening invoices, Delivery Note / Delivery Trip flows, mobile app screens, SMS/WhatsApp to customers.

## Data model

### DocType `Dispatch Log` (module Chundakadan)

One record per Sales Invoice. Not submittable. `track_changes = 1`. Naming: `DSP-.YY.-.#####`.

| Fieldname | Type | Notes |
|---|---|---|
| `sales_invoice` | Link Sales Invoice | reqd, unique, read-only |
| `company` | Link Company | read-only |
| `customer` | Link Customer | read-only |
| `customer_name` | Data | read-only |
| `contact_mobile` | Data | read-only; from the invoice's contact/customer address phone, for follow-up calls |
| `posting_date` | Date | invoice date, read-only |
| `grand_total` | Currency | read-only |
| `invoice_cancelled` | Check | read-only; set when the invoice is cancelled |
| `dispatch_status` | Select | `Pending` / `Dispatched` / `Customer Pickup` / `Delivered` / `Not Delivered`; default `Pending`; in list view + standard filter |
| `pending_reason` | Select | blank / `Stock Not Available` / `Payment Pending` / `Customer Asked to Hold` / `Transport Not Available` / `Other` |
| `pending_remarks` | Small Text | |
| `transporter` | Link Supplier | filter `is_transporter = 1` |
| `transporter_name` | Data | fetched from Supplier |
| `gst_transporter_id` | Data | fetched from Supplier |
| `vehicle_no` | Data | |
| `lr_no` | Data | |
| `lr_date` | Date | |
| `driver_name` | Data | |
| `mode_of_transport` | Select | `Road` / `Air` / `Rail` / `Ship`; default `Road` |
| `dispatched_on` | Datetime | set by server |
| `dispatched_by` | Link User | set by server |
| `expected_delivery` | Select | `Next Day` / `2 Days` / `After 2 Days` |
| `expected_delivery_date` | Date | computed from `dispatched_on` date (+1 / +2 / +3 calendar days); editable |
| `delivery_confirmed_on` | Datetime | set by server |
| `delivery_confirmed_by` | Link User | set by server |
| `delivery_remarks` | Small Text | |
| `ewaybill_sync_status` | Select | blank / `Not Required` / `Synced` / `Failed` |
| `ewaybill_sync_error` | Small Text | last error message |

### Sales Invoice

Custom field `dispatch_status` (Data, read-only, `allow_on_submit = 1`, `no_copy = 1`, in list view + standard filter), inserted in the Transporter Info section. Mirrors `Dispatch Log.dispatch_status`. Shipped as a Custom Field fixture (module Chundakadan).

### Role `Dispatch User`

Desk access. Shipped as a Role fixture.

## Behaviour

### Log creation

- `Sales Invoice.on_submit` hook `chundakadan.dispatch.events.create_dispatch_log`: if the invoice is in scope and has no log, insert a `Dispatch Log` (Pending) with invoice fields copied, and set `Sales Invoice.dispatch_status = "Pending"` via `db_set`. Wrapped in try/except; on failure write `frappe.log_error` and never block the submit.
- `Sales Invoice.on_cancel` hook `mark_invoice_cancelled`: set `invoice_cancelled = 1` on the log. The page hides cancelled logs.
- Patch `chundakadan.patches.backfill_dispatch_logs`: create Pending logs for in-scope invoices with `posting_date >= 2026-09-13` that have none. Idempotent.

### Status transitions (enforced in `Dispatch Log.validate`)

| From | To | Rule |
|---|---|---|
| Pending | Pending | reason may be set/changed |
| Pending | Dispatched | `transporter` required; server sets `dispatched_on/by`; `expected_delivery` required; `expected_delivery_date` computed if blank |
| Pending | Customer Pickup | no transporter; server sets `delivery_confirmed_on/by` (closed) |
| Dispatched | Delivered / Not Delivered | server sets `delivery_confirmed_on/by` |
| Not Delivered | Delivered | server sets `delivery_confirmed_on/by` |
| Not Delivered | Not Delivered | reschedule: new `expected_delivery_date` required |
| Dispatched | Dispatched | edit transport details |

Any other change throws. `pending_reason` is required when saving a Pending log that the dispatcher touched via the Reason action (enforced in the API, not in validate, so auto-created logs stay valid). Every save mirrors `dispatch_status` onto the Sales Invoice with `db_set`.

### Transport sync to Sales Invoice and e-Waybill

Runs after a log becomes or stays `Dispatched` with changed transport fields (`chundakadan.dispatch.sync.sync_transport`):

- If the invoice has no `ewaybill`: `db_set` `transporter`, `transporter_name`, `gst_transporter_id`, `vehicle_no`, `lr_no`, `lr_date`, `driver_name`, `mode_of_transport` on the Sales Invoice; `ewaybill_sync_status = "Not Required"`.
- If the invoice has an `ewaybill`: call India Compliance `update_transporter` (when transporter/GST transporter ID changed) and `update_vehicle_info` (when vehicle/LR/mode changed) from `india_compliance.gst_india.utils.e_waybill`. These update the portal and the invoice fields. On success `Synced`; on exception `Failed` with the message in `ewaybill_sync_error`. The log save itself is not rolled back.
- `retry_sync(log)` re-runs the sync.

## Dispatch page

Desk Page `dispatch` (title "Dispatch"), roles: Dispatch User, System Manager, Accounts Manager, Sales Manager. Files under `chundakadan/chundakadan/page/dispatch/`.

- Count cards: Pending, Follow-up Today, Dispatched, Not Delivered, Delivered Today. Clicking a card opens its tab.
- Filters: invoice date range, customer, transporter, text search on invoice no / customer name.
- Tabs and rows:
  - **Pending** — invoice, date, customer, amount, days pending, reason. Actions: Dispatch, Reason, Customer Pickup. Rows pending more than 2 days are highlighted red.
  - **Follow-up Today** — status Dispatched or Not Delivered with `expected_delivery_date <= today`; shows customer mobile. Actions: Delivered, Not Delivered.
  - **Dispatched** — transporter, vehicle, LR, dispatched on, expected date, e-Waybill sync status. Actions: Confirm Delivery, Edit Transport, Retry Sync (only when Failed).
  - **Not Delivered** — remarks, expected date. Actions: Delivered, Reschedule.
  - **Delivered** — delivered on, confirmed by, remarks; read-only.
- Each action opens a `frappe.ui.Dialog`, calls a whitelisted method, and refreshes only that tab and the counts.
- Invoice number links to the Sales Invoice form. Tables scroll horizontally on small screens.

### Whitelisted API (`chundakadan.dispatch.api`)

All check `frappe.has_permission("Dispatch Log", "write")` (reads check `read`) and operate on one log by name.

- `get_counts(filters)`
- `get_logs(tab, filters, start, page_length)` — page_length 50
- `set_pending_reason(log, reason, remarks)`
- `mark_dispatched(log, transporter, vehicle_no, lr_no, lr_date, driver_name, mode_of_transport, expected_delivery, expected_delivery_date=None)`
- `mark_customer_pickup(log, remarks=None)`
- `confirm_delivery(log, delivered, remarks=None, new_expected_date=None)` — `delivered` bool; Not Delivered requires `new_expected_date`
- `update_transport(log, ...)` — same fields as dispatch, status stays Dispatched
- `retry_sync(log)`

## Permissions

| Role | Dispatch Log | Dispatch page | Sales Invoice |
|---|---|---|---|
| Dispatch User | read, write | yes | read |
| Accounts User, Sales User | read | no | unchanged |
| Accounts Manager, Sales Manager | read | yes (view) | unchanged |
| System Manager | read, write | yes | unchanged |

Nobody has delete on Dispatch Log. Dispatch User also needs read on Supplier and Customer (added as Custom DocPerm via install hook if missing).

## Error handling

- Log creation never blocks invoice submit; failures go to Error Log.
- Transition rule violations throw user-facing messages.
- e-Waybill failures are stored on the log and shown on the page with Retry.
- Unique constraint on `sales_invoice` prevents duplicates, including concurrent submits.

## Testing

- Unit tests (`test_dispatch_log.py`): log created for CA invoice; not for Home Stop, return, opening; cancel flag; transporter required for Dispatched; expected date computation; invalid transitions rejected; status mirrored on invoice.
- Sync tests with India Compliance calls mocked: no-ewaybill path writes invoice fields; ewaybill path calls both functions; exception sets Failed.
- Manual verification on the old server copy against a real invoice inside a rolled-back transaction. No live portal calls.

## Deployment

1. Push app changes (DocType, Page, API, hooks, fixtures for Role + Custom Field, patch).
2. On Frappe Cloud: Apps → chundakadan → Update (runs migrate, fixtures, backfill patch).
3. Business setup: mark the 4–5 transport partners as Supplier with **Is Transporter**; assign **Dispatch User** role to dispatch staff.
