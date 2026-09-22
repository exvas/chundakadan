frappe.listview_settings["Post Dated Cheque"] = {
	add_fields: ["status", "cheque_date", "amount"],
	get_indicator(doc) {
		const colours = { Draft: "red", Pending: "orange", Collected: "green", Returned: "red", Bounced: "red", Cancelled: "grey" };
		return [__(doc.status), colours[doc.status] || "blue", "status,=," + doc.status];
	},
};
