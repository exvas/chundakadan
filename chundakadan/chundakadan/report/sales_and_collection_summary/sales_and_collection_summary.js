// Copyright (c) 2026, Chundakadan and contributors
frappe.query_reports["Sales and Collection Summary"] = {
	filters: [
		{
			fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company",
			default: frappe.defaults.get_user_default("Company"), reqd: 1,
		},
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{
			fieldname: "group_by", label: __("Group By"), fieldtype: "Select",
			options: ["Sales Person", "Brand", "Customer", "Day", "Month"],
			default: "Sales Person", reqd: 1,
		},
		{ fieldname: "sales_person", label: __("Sales Person"), fieldtype: "Link", options: "Sales Person" },
		{ fieldname: "brand", label: __("Brand"), fieldtype: "Link", options: "Brand" },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "balance" && data && data.balance > 0) {
			// still to be collected
			value = `<span style="color: var(--orange-500)">${value}</span>`;
		}
		return value;
	},
};
