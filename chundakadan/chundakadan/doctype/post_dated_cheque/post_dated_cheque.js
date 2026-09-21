// Copyright (c) 2026, Chundakadan and contributors
frappe.ui.form.on("Post Dated Cheque", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status === "Collected" && frm.doc.payment_entry) {
			// a collected cheque that bounced needs the accounting reversal,
			// which Cheque Bounce does against the Payment Entry
			frm.add_custom_button(__("Cheque Bounced"), () => {
				frappe.new_doc("Cheque Bounce", {
					payment_entry: frm.doc.payment_entry,
					customer: frm.doc.customer,
					cheque_no: frm.doc.cheque_no,
					cheque_date: frm.doc.cheque_date,
					original_amount: frm.doc.amount,
					bounce_date: frappe.datetime.get_today(),
					mode_of_payment: "Cheque",
				});
			});
		}
		if (frm.doc.cheque_bounce) {
			frm.add_custom_button(__("Cheque Bounce"), () => frappe.set_route("Form", "Cheque Bounce", frm.doc.cheque_bounce), __("View"));
		}
		if (frm.doc.docstatus === 1 && frm.doc.status === "Pending") {
			frm.add_custom_button(__("Cheque Collected"), () => collect_dialog(frm)).addClass("btn-primary");
			frm.add_custom_button(__("Cheque Bounced"), () => bounce_dialog(frm));
		}
		if (frm.doc.payment_entry) {
			frm.add_custom_button(__("Payment Entry"), () => frappe.set_route("Form", "Payment Entry", frm.doc.payment_entry), __("View"));
		}
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("New Customer Bank Account"), () => new_bank_account_dialog(frm));
		}
		set_status_indicator(frm);
	},

	setup(frm) {
		// this customer's accounts first, plus any not yet owned by anyone —
		// picking one of those ties it to this customer on save
		frm.set_query("bank_account", () => ({
			query: "chundakadan.chundakadan.doctype.post_dated_cheque.post_dated_cheque.customer_bank_accounts",
			filters: { customer: frm.doc.customer || "" },
		}));
		// no "Create a new Bank Account" jump from the dropdown — everything
		// is entered in the dialog on this form
		if (frm.fields_dict.bank_account) frm.fields_dict.bank_account.df.only_select = 1;
		// only this customer's open invoices
		frm.set_query("sales_invoice", "references", () => ({
			filters: {
				customer: frm.doc.customer || "",
				company: frm.doc.company || "",
				docstatus: 1,
				outstanding_amount: [">", 0],
			},
		}));
	},

	customer(frm) {
		frm.clear_table("references");
		frm.refresh_field("references");
		if (frm.doc.bank_account) frm.set_value("bank_account", null);
	},

	bank_account_button(frm) {
		new_bank_account_dialog(frm);
	},
});

frappe.ui.form.on("Post Dated Cheque Reference", {
	sales_invoice(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.sales_invoice) return;
		frappe.db.get_value("Sales Invoice", row.sales_invoice, "outstanding_amount").then((r) => {
			frappe.model.set_value(cdt, cdn, "outstanding_amount", r.message.outstanding_amount);
			if (!row.allocated_amount) frappe.model.set_value(cdt, cdn, "allocated_amount", r.message.outstanding_amount);
		});
	},
});

function set_status_indicator(frm) {
	const colours = { Draft: "red", Pending: "orange", Collected: "green", Bounced: "red", Cancelled: "grey" };
	if (frm.doc.docstatus === 1) frm.page.set_indicator(__(frm.doc.status), colours[frm.doc.status] || "blue");
}

function collect_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Cheque Collected — {0}", [frm.doc.cheque_no]),
		fields: [
			{
				fieldtype: "Link", fieldname: "mode_of_payment", label: __("Mode of Payment"), options: "Mode of Payment", reqd: 1, default: "Cheque",
				onchange: () => set_deposit_account(dialog, frm),
			},
			{
				fieldtype: "Link", fieldname: "bank_account", label: __("Deposited To (Bank Account)"), options: "Account", reqd: 1, read_only: 1,
				description: __("From the Mode of Payment's account for this company"),
			},
			{ fieldtype: "Column Break" },
			{ fieldtype: "Date", fieldname: "posting_date", label: __("Payment Date"), reqd: 1, default: frm.doc.cheque_date },
			{ fieldtype: "Data", fieldname: "reference_no", label: __("Reference No"), default: frm.doc.cheque_no, reqd: 1 },
			{ fieldtype: "Date", fieldname: "reference_date", label: __("Reference Date"), default: frm.doc.cheque_date, reqd: 1 },
			{ fieldtype: "Section Break" },
			{ fieldtype: "Small Text", fieldname: "remarks", label: __("Remarks") },
		],
		primary_action_label: __("Create Payment Entry"),
		primary_action: (values) => {
			dialog.hide();
			frappe.call({
				method: "chundakadan.chundakadan.doctype.post_dated_cheque.post_dated_cheque.collect",
				args: Object.assign({ cheque: frm.doc.name }, values),
				freeze: true,
				freeze_message: __("Creating Payment Entry..."),
			}).then((r) => {
				if (!r.message) return;
				frappe.show_alert({ message: __("Payment Entry {0} created", [r.message.payment_entry]), indicator: "green" });
				frm.reload_doc();
			});
		},
	});
	dialog.show();
	set_deposit_account(dialog, frm);
}

// The account money lands in comes from the Mode of Payment's row for this
// company, so the user picks the mode, not the ledger.
function set_deposit_account(dialog, frm) {
	const mode = dialog.get_value("mode_of_payment");
	if (!mode) {
		dialog.set_value("bank_account", "");
		return;
	}
	frappe.db
		.get_value("Mode of Payment Account", { parent: mode, company: frm.doc.company }, "default_account")
		.then((r) => {
			const account = r.message && r.message.default_account;
			dialog.set_value("bank_account", account || "");
			if (!account) {
				frappe.msgprint(
					__("Mode of Payment {0} has no account for {1}. Set it in Mode of Payment.", [mode, frm.doc.company])
				);
			}
		});
}

function bounce_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Cheque Bounced — {0}", [frm.doc.cheque_no]),
		fields: [{ fieldtype: "Small Text", fieldname: "reason", label: __("Reason"), reqd: 1 }],
		primary_action_label: __("Mark Bounced"),
		primary_action: (values) => {
			dialog.hide();
			frappe.call({
				method: "chundakadan.chundakadan.doctype.post_dated_cheque.post_dated_cheque.mark_bounced",
				args: { cheque: frm.doc.name, reason: values.reason },
				freeze: true,
			}).then(() => frm.reload_doc());
		},
	});
	dialog.show();
}

function new_bank_account_dialog(frm) {
	if (!frm.doc.customer) {
		frappe.msgprint(__("Pick the customer first."));
		return;
	}
	const dialog = new frappe.ui.Dialog({
		title: __("New Bank Account — {0}", [frm.doc.customer_name || frm.doc.customer]),
		fields: [
			{ fieldtype: "Autocomplete", fieldname: "bank", label: __("Bank"), reqd: 1, options: [], description: __("Type the bank name; a new one is created if it does not exist") },
			{ fieldtype: "Data", fieldname: "account_name", label: __("Account Name"), default: frm.doc.customer_name || frm.doc.customer },
			{ fieldtype: "Column Break" },
			{ fieldtype: "Data", fieldname: "bank_account_no", label: __("Account No") },
			{ fieldtype: "Data", fieldname: "ifsc", label: __("IFSC") },
			{ fieldtype: "Data", fieldname: "branch", label: __("Branch") },
		],
		primary_action_label: __("Create"),
		primary_action: (values) => {
			frappe.call({
				method: "chundakadan.chundakadan.doctype.post_dated_cheque.post_dated_cheque.create_customer_bank_account",
				args: Object.assign({ customer: frm.doc.customer }, values),
				freeze: true,
			}).then((r) => {
				if (!r.message) return;
				dialog.hide();
				frm.set_value("bank_account", r.message.name);
				frappe.show_alert({
					message: r.message.created ? __("Bank Account {0} created", [r.message.name]) : __("Using existing Bank Account {0}", [r.message.name]),
					indicator: "green",
				});
			});
		},
	});
	dialog.show();
	// suggest the banks already on file, without leaving this form
	frappe.db.get_list("Bank", { fields: ["name"], limit: 200, order_by: "name asc" }).then((banks) => {
		dialog.set_df_property("bank", "options", (banks || []).map((b) => b.name));
	});
}
