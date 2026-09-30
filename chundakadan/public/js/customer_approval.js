// Copyright (c) 2026, Chundakadan and contributors
// Approve / Reject on the Customer form, for the one role named in
// Chundakadan Settings. Everyone else sees nothing new.
frappe.provide("chundakadan.customer_approval");

// One call per desk session — the answer only changes when Settings change.
chundakadan.customer_approval.access = function () {
	if (!chundakadan.customer_approval._promise) {
		chundakadan.customer_approval._promise = frappe
			.xcall("chundakadan.chundakadan.api.customer_approval.access")
			.catch(() => ({ enabled: false, can_approve: false }));
	}
	return chundakadan.customer_approval._promise;
};

frappe.ui.form.on("Customer", {
	refresh(frm) {
		if (frm.is_new()) return;
		const status = frm.doc.custom_approval_status;
		if (!status) return;

		const colour = { Pending: "orange", Approved: "green", Rejected: "red" }[status];
		if (colour) frm.dashboard.set_headline_alert(__("Approval: {0}", [__(status)]), colour);

		if (status !== "Pending") return;
		chundakadan.customer_approval.access().then((access) => {
			if (!access.can_approve || frm.doc.custom_approval_status !== "Pending") return;

			frm.add_custom_button(__("Approve"), () => approve(frm)).addClass("btn-primary");
			frm.add_custom_button(__("Reject"), () => reject(frm));
		});
	},
});

function approve(frm) {
	frappe.confirm(
		__("Approve {0}? It will be enabled and orders can then be raised against it.", [frm.doc.name]),
		() => {
			frappe
				.xcall("chundakadan.chundakadan.api.customer_approval.approve", { customers: [frm.doc.name] })
				.then(() => {
					frappe.show_alert({ message: __("Customer approved"), indicator: "green" });
					frm.reload_doc();
				});
		}
	);
}

function reject(frm) {
	frappe.prompt(
		[{ fieldname: "reason", label: __("Reason"), fieldtype: "Small Text", reqd: 1 }],
		(values) => {
			frappe
				.xcall("chundakadan.chundakadan.api.customer_approval.reject", {
					customers: [frm.doc.name],
					reason: values.reason,
				})
				.then(() => {
					frappe.show_alert({ message: __("Customer rejected"), indicator: "red" });
					frm.reload_doc();
				});
		},
		__("Reject Customer"),
		__("Reject")
	);
}
