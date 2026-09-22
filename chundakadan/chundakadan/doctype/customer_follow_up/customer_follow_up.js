// Copyright (c) 2026, Chundakadan and contributors
const API = "chundakadan.chundakadan.doctype.customer_follow_up.customer_follow_up";

frappe.ui.form.on("Customer Follow Up", {
	refresh(frm) {
		render_history(frm);
		if (frm.doc.customer && !frm.is_new()) {
			frm.add_custom_button(__("Customer Ledger"), () =>
				frappe.set_route("query-report", "Account Ledger Report", { party: frm.doc.customer }), __("View"));
		}
		if (frm.doc.todo) {
			frm.add_custom_button(__("Task"), () => frappe.set_route("Form", "ToDo", frm.doc.todo), __("View"));
		}
		if (frm.doc.status === "Open") frm.page.set_indicator(__("Open"), "orange");
		else frm.page.set_indicator(__(frm.doc.outcome === "Paid" ? "Paid" : "Closed"), frm.doc.outcome === "Paid" ? "green" : "grey");
	},

	customer(frm) {
		if (!frm.doc.customer) {
			frm.set_value("outstanding_amount", 0);
			return;
		}
		frappe.call({
			method: `${API}.customer_outstanding`,
			args: { customer: frm.doc.customer, company: frm.doc.company },
		}).then((r) => frm.set_value("outstanding_amount", r.message || 0));
		render_history(frm);
	},

	company(frm) {
		if (frm.doc.customer) frm.trigger("customer");
	},

	outcome(frm) {
		// paid closes the chase, so no next date is needed
		frm.set_df_property("next_follow_up_date", "reqd", frm.doc.outcome !== "Paid");
		if (frm.doc.outcome === "Paid") frm.set_value("next_follow_up_date", null);
		else if (!frm.doc.next_follow_up_date) {
			frm.set_value("next_follow_up_date", frappe.datetime.add_days(frappe.datetime.get_today(), 7));
		}
	},
});

function render_history(frm) {
	const wrapper = frm.get_field("remarks") && frm.dashboard;
	if (!frm.doc.customer || !wrapper) return;
	frappe.call({
		method: `${API}.chase_history`,
		args: { customer: frm.doc.customer, company: frm.doc.company, limit: 5 },
	}).then((r) => {
		const rows = (r.message || []).filter((row) => row.name !== frm.doc.name);
		frm.dashboard.clear_headline();
		if (!rows.length) return;
		const html = rows
			.map((row) => {
				const amount = format_currency(row.outstanding_amount || 0);
				const next = row.next_follow_up_date ? ` · next ${frappe.datetime.str_to_user(row.next_follow_up_date)}` : "";
				const remarks = row.remarks ? ` — ${frappe.utils.escape_html(row.remarks)}` : "";
				return `<div style="margin:2px 0">${frappe.datetime.str_to_user(row.follow_up_date)} · <b>${row.outcome}</b> · ${amount}${next}${remarks}</div>`;
			})
			.join("");
		frm.dashboard.set_headline(`<div><b>${__("Chase history")}</b>${html}</div>`, "blue");
	});
}
