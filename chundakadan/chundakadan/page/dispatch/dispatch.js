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
				{ fieldtype: "Button", fieldname: "new_transporter", label: __("+ New Transporter"), click: () => this.new_transporter_dialog((name) => dialog.set_value("transporter", name)) },
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

	new_transporter_dialog(on_created) {
		const dialog = new frappe.ui.Dialog({
			title: __("New Transporter"),
			fields: [
				{ fieldtype: "Data", fieldname: "transporter_name", label: __("Transporter Name"), reqd: 1 },
				{ fieldtype: "Data", fieldname: "gst_transporter_id", label: __("GST Transporter ID"), description: __("Optional. 15 characters, needed to update the e-Waybill transporter") },
			],
			primary_action_label: __("Create"),
			primary_action: (values) => {
				frappe
					.call({ method: `${DISPATCH_API}.create_transporter`, args: values, freeze: true })
					.then((r) => {
						dialog.hide();
						frappe.show_alert({ message: __("Transporter {0} saved", [r.message.supplier_name]), indicator: "green" });
						on_created(r.message.name);
					});
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
