frappe.listview_settings["Customer Follow Up"] = {
	add_fields: ["status", "outcome", "next_follow_up_date"],
	get_indicator(doc) {
		if (doc.status === "Closed") {
			return [__(doc.outcome === "Paid" ? "Paid" : "Closed"), doc.outcome === "Paid" ? "green" : "grey", "status,=,Closed"];
		}
		const overdue = doc.next_follow_up_date && doc.next_follow_up_date < frappe.datetime.get_today();
		return [__(overdue ? "Overdue" : "Open"), overdue ? "red" : "orange", "status,=,Open"];
	},
};
