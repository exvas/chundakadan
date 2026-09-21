// Copyright (c) 2026, Chundakadan and contributors
frappe.query_reports["Post Dated Cheque Report"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
		{ fieldname: "from_date", label: __("Cheque Date From"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("Cheque Date To"), fieldtype: "Date" },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "sales_person", label: __("Sales Person"), fieldtype: "Link", options: "Sales Person" },
		{ fieldname: "status", label: __("Status"), fieldtype: "Select", options: ["", "Draft", "Pending", "Collected", "Bounced", "Cancelled"].join("\n"), default: "Pending" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "status" && data) {
			const colours = { Pending: "orange", Collected: "green", Bounced: "red", Cancelled: "grey", Draft: "red" };
			value = `<span style="color:var(--text-on-${colours[data.status] || "blue"}, inherit);font-weight:600">${value}</span>`;
		}
		if (column.fieldname === "days_to_due" && data && data.status === "Pending" && data.days_to_due < 0) {
			value = `<span style="color:var(--red-500)">${value}</span>`;
		}
		return value;
	},
};
