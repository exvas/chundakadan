// Copyright (c) 2026, Chundakadan and contributors
frappe.query_reports["Daily Work Summary Status"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), -6), reqd: 1 },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
		{ fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department" },
		{ fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee" },
		{ fieldname: "only_missing", label: __("Only Not Submitted"), fieldtype: "Check", default: 0 },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "status" && data) {
			const colour = {
				"Not Submitted": "var(--red-500)",
				Draft: "var(--orange-500)",
				Returned: "var(--orange-500)",
				Approved: "var(--green-500)",
			}[data.status];
			if (colour) value = `<span style="color:${colour}">${value}</span>`;
		}
		return value;
	},
};
