// Copyright (c) 2026, Chundakadan and contributors
// Bulk approve / reject from the Item list, for the approval role only.
frappe.listview_settings["Item"] = frappe.listview_settings["Item"] || {};

const chundakadan_item_indicator = {
	Pending: "orange",
	Rejected: "red",
};

frappe.listview_settings["Item"].onload = function (listview) {
	frappe
		.xcall("chundakadan.chundakadan.api.item_approval.access")
		.then((access) => {
			if (!access || !access.can_approve) return;

			listview.page.add_action_item(__("Approve Items"), () => {
				const names = listview.get_checked_items(true);
				if (!names.length) return;
				frappe.confirm(
					__("Approve {0} item(s)? They will be enabled.", [names.length]),
					() => {
						frappe
							.xcall("chundakadan.chundakadan.api.item_approval.approve", { items: names })
							.then((r) => {
								frappe.show_alert({
									message: __("{0} item(s) approved", [r.approved.length]),
									indicator: "green",
								});
								listview.refresh();
							});
					}
				);
			});

			listview.page.add_action_item(__("Reject Items"), () => {
				const names = listview.get_checked_items(true);
				if (!names.length) return;
				frappe.prompt(
					[{ fieldname: "reason", label: __("Reason"), fieldtype: "Small Text", reqd: 1 }],
					(values) => {
						frappe
							.xcall("chundakadan.chundakadan.api.item_approval.reject", {
								items: names,
								reason: values.reason,
							})
							.then((r) => {
								frappe.show_alert({
									message: __("{0} item(s) rejected", [r.rejected.length]),
									indicator: "red",
								});
								listview.refresh();
							});
					},
					__("Reject Items"),
					__("Reject")
				);
			});
		})
		.catch(() => {});
};

frappe.listview_settings["Item"].get_indicator = function (doc) {
	const colour = chundakadan_item_indicator[doc.custom_approval_status];
	if (colour) {
		return [__(doc.custom_approval_status), colour, "custom_approval_status,=," + doc.custom_approval_status];
	}
	if (doc.disabled) return [__("Disabled"), "grey", "disabled,=,1"];
	return [__("Enabled"), "blue", "disabled,=,0"];
};
