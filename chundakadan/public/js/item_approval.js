// Copyright (c) 2026, Chundakadan and contributors
// Approve / Reject on the Item form, for the one role named in
// Chundakadan Settings. Everyone else sees nothing new.
frappe.provide("chundakadan.item_approval");

// One call per desk session — the answer only changes when Settings change.
chundakadan.item_approval.access = function () {
	if (!chundakadan.item_approval._promise) {
		chundakadan.item_approval._promise = frappe
			.xcall("chundakadan.chundakadan.api.item_approval.access")
			.catch(() => ({ enabled: false, can_approve: false }));
	}
	return chundakadan.item_approval._promise;
};

frappe.ui.form.on("Item", {
	refresh(frm) {
		if (frm.is_new()) return;
		const status = frm.doc.custom_approval_status;
		if (!status) return;

		const colour = { Pending: "orange", Approved: "green", Rejected: "red" }[status];
		if (colour) frm.dashboard.set_headline_alert(__("Approval: {0}", [__(status)]), colour);

		if (status !== "Pending") return;
		chundakadan.item_approval.access().then((access) => {
			if (!access.can_approve || frm.doc.custom_approval_status !== "Pending") return;

			frm.add_custom_button(__("Approve"), () => approve(frm)).addClass("btn-primary");
			frm.add_custom_button(__("Reject"), () => reject(frm));
		});
	},
});

function approve(frm) {
	frappe.confirm(
		__("Approve {0}? It will be enabled and can then be used on transactions.", [frm.doc.name]),
		() => {
			frappe
				.xcall("chundakadan.chundakadan.api.item_approval.approve", { items: [frm.doc.name] })
				.then(() => {
					frappe.show_alert({ message: __("Item approved"), indicator: "green" });
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
				.xcall("chundakadan.chundakadan.api.item_approval.reject", {
					items: [frm.doc.name],
					reason: values.reason,
				})
				.then(() => {
					frappe.show_alert({ message: __("Item rejected"), indicator: "red" });
					frm.reload_doc();
				});
		},
		__("Reject Item"),
		__("Reject")
	);
}
