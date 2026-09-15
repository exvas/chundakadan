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
