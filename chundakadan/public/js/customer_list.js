// Copyright (c) 2026, Chundakadan and contributors
// Bulk approve / reject from the Customer list, for the approval role only.
frappe.listview_settings["Customer"] = frappe.listview_settings["Customer"] || {};
frappe.listview_settings["Customer"].add_fields = ["custom_approval_status", "disabled"];

const chundakadan_customer_indicator = {
	Pending: "orange",
	Rejected: "red",
};

frappe.listview_settings["Customer"].onload = function (listview) {
	frappe
		.xcall("chundakadan.chundakadan.api.customer_approval.access")
		.then((access) => {
			if (!access || !access.can_approve) return;

			listview.page.add_action_item(__("Approve Customers"), () => {
				const names = listview.get_checked_items(true);
				if (!names.length) return;
				frappe.confirm(
					__("Approve {0} customer(s)? They will be enabled.", [names.length]),
					() => {
						frappe
							.xcall("chundakadan.chundakadan.api.customer_approval.approve", { customers: names })
							.then((r) => {
								frappe.show_alert({
									message: __("{0} customer(s) approved", [r.approved.length]),
									indicator: "green",
								});
								listview.refresh();
							});
					}
				);
			});

			listview.page.add_action_item(__("Reject Customers"), () => {
				const names = listview.get_checked_items(true);
				if (!names.length) return;
				frappe.prompt(
					[{ fieldname: "reason", label: __("Reason"), fieldtype: "Small Text", reqd: 1 }],
					(values) => {
						frappe
							.xcall("chundakadan.chundakadan.api.customer_approval.reject", {
								customers: names,
								reason: values.reason,
							})
							.then((r) => {
								frappe.show_alert({
									message: __("{0} customer(s) rejected", [r.rejected.length]),
									indicator: "red",
								});
								listview.refresh();
							});
					},
					__("Reject Customers"),
					__("Reject")
				);
			});
		})
		.catch(() => {});
};

frappe.listview_settings["Customer"].get_indicator = function (doc) {
	const colour = chundakadan_customer_indicator[doc.custom_approval_status];
	if (colour) {
		return [__(doc.custom_approval_status), colour, "custom_approval_status,=," + doc.custom_approval_status];
	}
	if (doc.disabled) return [__("Disabled"), "grey", "disabled,=,1"];
	return [__("Enabled"), "blue", "disabled,=,0"];
};
