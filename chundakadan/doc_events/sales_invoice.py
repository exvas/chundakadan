import frappe

from chundakadan.doc_events.stock_control import get_update_stock

def validate_sales_invoice(doc, method):
	if doc.is_return or doc.get("custom_ignore_overdue_restriction"):
		return

	restriction_enabled = frappe.db.get_value("Customer", doc.customer, "custom_overdue_invoice_restriction")
	if not restriction_enabled:
		return

	overdue_invoices = check_overdue_unpaid_invoices(doc.customer, doc.posting_date)
	if overdue_invoices:
		invoice_list = "<ul>" + "".join([f"<li>{d.name} (Due: {d.due_date}, Outstanding: {d.outstanding_amount})</li>" for d in overdue_invoices]) + "</ul>"
		frappe.throw(
			f"Customer <b>{doc.customer}</b> has overdue unpaid invoices based on their payment schedule as of {doc.posting_date}:<br><br>{invoice_list}<br>"
			f"Please clear these outstanding payments before creating a new Sales Invoice.",
			title="Credit Restriction"
		)

@frappe.whitelist()
def check_overdue_unpaid_invoices(customer, posting_date=None):
	# Check if restriction is enabled for this customer
	restriction_enabled = frappe.db.get_value("Customer", customer, "custom_overdue_invoice_restriction")
	if not restriction_enabled:
		return []

	if not posting_date:
		posting_date = frappe.utils.today()

	# Find invoices where at least one payment schedule date has passed relative to the posting_date and there is still an outstanding amount
	overdue_invoices = frappe.db.sql("""
		SELECT DISTINCT si.name, ps.due_date, si.outstanding_amount
		FROM `tabSales Invoice` si
		JOIN `tabPayment Schedule` ps ON ps.parent = si.name
		WHERE si.docstatus = 1
		  AND si.customer = %s
		  AND si.outstanding_amount > 0
		  AND ps.due_date < %s
		ORDER BY ps.due_date ASC
	""", (customer, posting_date), as_dict=1)
	
	return overdue_invoices

def autoname(doc, method):
	from frappe.model.naming import make_autoname
	
	if doc.is_return:
		doc.custom_naming_series1 = "SR-.YY.-.####"
	else:
		doc.custom_naming_series1 = "SI-.YY.-.####"
		
	# Generate the name explicitly to ensure it works even if the Customize Form is misconfigured
	if not doc.name:
		doc.name = make_autoname(doc.custom_naming_series1, doc=doc)

def on_trash(doc, method):
	import frappe
	if doc.custom_naming_series1 and doc.name:
		try:
			frappe.model.naming.revert_series_if_last(doc.custom_naming_series1, doc.name)
		except Exception:
			pass


def enforce_b2b_billing(doc, method):
	"""B2B-only billing for company Chundakadan Agencies: require Customer GSTIN + Address.
	Migrated from a Server Script so it also works on Frappe Cloud (where server
	scripts may be disabled). Toggle: Chundakadan Settings > enforce_b2b_gstin_billing."""
	if not frappe.db.get_single_value("Chundakadan Settings", "enforce_b2b_gstin_billing"):
		return
	if doc.company != "Chundakadan Agencies":
		return
	gstin = (doc.get("billing_address_gstin") or "").strip()
	if not gstin and doc.get("customer"):
		gstin = (frappe.db.get_value("Customer", doc.customer, "gstin") or "").strip()
	if not doc.get("customer_address"):
		frappe.throw(
			"Chundakadan Agencies: cannot bill this customer - no Address. "
			"Add a billing address (B2B only)."
		)
	if not gstin:
		frappe.throw(
			"Chundakadan Agencies: cannot bill this customer - no GSTIN/UIN. "
			"Only B2B (registered) customers can be billed."
		)


# Default stock warehouse per company for Sales Invoice (Update Stock always on).
COMPANY_STORE_WAREHOUSE = {
	"Chundakadan Agencies": "Stores - CA",
	"Chundakadan Home Stop": "Stores - CHS",
}


def apply_stock_defaults(doc, method=None):
	"""before_validate on Sales Invoice: tick Update Stock and set the company's
	Stores warehouse on the header and item rows.

	Skipped for opening invoices (ERPNext does not allow Update Stock there) and
	for invoices made against a Delivery Note (stock already moved by the DN)."""
	if doc.docstatus != 0 or doc.get("is_opening") == "Yes":
		return
	if any(row.get("delivery_note") for row in doc.get("items") or []):
		return

	warehouse = COMPANY_STORE_WAREHOUSE.get(doc.company)
	if not warehouse or not frappe.db.exists("Warehouse", warehouse):
		return

	# Update Stock is not the user's choice: Chundakadan Settings decides it.
	# With the setting off, stock leaves through the Delivery Note created on
	# submit (auto_create_delivery_note).
	doc.update_stock = get_update_stock("Sales Invoice")

	def belongs_to_company(wh):
		return wh and frappe.get_cached_value("Warehouse", wh, "company") == doc.company

	if not belongs_to_company(doc.get("set_warehouse")):
		doc.set_warehouse = warehouse
	for row in doc.get("items") or []:
		if not belongs_to_company(row.get("warehouse")):
			row.warehouse = doc.set_warehouse


def auto_create_delivery_note(doc, method=None):
	"""on_submit on Sales Invoice: move the stock through a Delivery Note.

	Invoices no longer tick Update Stock, so the goods leave the warehouse on
	this Delivery Note. Invoices that already updated stock themselves (older
	or manually ticked ones) are skipped so stock is never reduced twice.
	Failures never block the invoice: the note is left as a draft and logged.
	"""
	if doc.get("update_stock") or doc.get("is_return") or doc.get("is_opening") == "Yes":
		return
	if doc.company not in COMPANY_STORE_WAREHOUSE:
		return
	if frappe.db.exists("Delivery Note Item", {"against_sales_invoice": doc.name, "docstatus": ["<", 2]}):
		return
	if not any(
		frappe.get_cached_value("Item", row.item_code, "is_stock_item") for row in doc.get("items") or []
	):
		return

	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note

	note = None
	try:
		note = make_delivery_note(doc.name)
		note.posting_date = doc.posting_date
		note.posting_time = doc.posting_time
		note.set_posting_time = 1
		note.flags.ignore_permissions = True
		note.insert(ignore_permissions=True)
		note.submit()
	except Exception:
		frappe.log_error(title=f"Auto Delivery Note failed for {doc.name}")
		frappe.msgprint(
			frappe._("Delivery Note could not be created for {0}. Please create it manually.").format(doc.name),
			indicator="orange",
			alert=True,
		)


@frappe.whitelist()
def backfill_delivery_notes(name_like=None, limit=None, dry_run=0):
	"""Create the missing Delivery Notes for already-submitted invoices.

	auto_create_delivery_note only fires on submit, so invoices submitted
	before it was deployed never moved their stock. This walks those
	invoices and creates the note for each one, skipping any that already
	have a note. Safe to run again: it only touches invoices with none.

	    bench --site <site> execute chundakadan.doc_events.sales_invoice.backfill_delivery_notes --kwargs \"{name_like: SI-CA-26-%, dry_run: 1}\"

	Returns {"created": [...], "skipped": [...], "failed": [...]}.
	"""
	frappe.only_for("System Manager")
	dry_run = frappe.utils.cint(dry_run)

	filters = {
		"docstatus": 1,
		"update_stock": 0,
		"is_return": 0,
		"is_opening": ["!=", "Yes"],
		"company": ["in", list(COMPANY_STORE_WAREHOUSE)],
	}
	if name_like:
		filters["name"] = ["like", name_like]

	names = frappe.get_all(
		"Sales Invoice",
		filters=filters,
		pluck="name",
		order_by="posting_date asc, name asc",
		limit_page_length=frappe.utils.cint(limit) or 0,
	)

	created, skipped, failed = [], [], []
	for name in names:
		if _linked_delivery_note(name):
			skipped.append(name)
			continue
		if dry_run:
			created.append(name)
			continue
		auto_create_delivery_note(frappe.get_doc("Sales Invoice", name))
		note = _linked_delivery_note(name)
		if note and frappe.db.get_value("Delivery Note", note, "docstatus") == 1:
			created.append(name)
		else:
			failed.append({"sales_invoice": name, "draft_delivery_note": note})

	return {"created": created, "skipped": skipped, "failed": failed, "dry_run": bool(dry_run)}


def _linked_delivery_note(invoice):
	return frappe.db.get_value(
		"Delivery Note Item", {"against_sales_invoice": invoice, "docstatus": ["<", 2]}, "parent"
	)
