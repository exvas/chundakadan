// Copyright (c) 2026, Chundakadan and contributors
frappe.listview_settings["Daily Work Summary"] = {
	add_fields: ["custom_approval_status", "docstatus"],
	get_indicator(doc) {
		const colours = {
			Draft: "grey",
			Pending: "orange",
			"Partially Approved": "blue",
			Approved: "green",
			Returned: "yellow",
			Rejected: "red",
		};
		const status = doc.custom_approval_status || "Draft";
		return [__(status), colours[status] || "grey", "custom_approval_status,=," + status];
	},
};
