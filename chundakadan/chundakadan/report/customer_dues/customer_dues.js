// Copyright (c) 2026, Chundakadan and contributors
frappe.query_reports["Customer Dues"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "sales_person",
			label: __("Sales Person"),
			fieldtype: "Link",
			options: "Sales Person",
		},
		{
			fieldname: "territory",
			label: __("Territory"),
			fieldtype: "Link",
			options: "Territory",
		},
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{
			fieldname: "detail",
			label: __("Invoice Detail"),
			fieldtype: "Check",
			// one row per open invoice instead of one per customer
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "days_overdue" && data && data.days_overdue > 0) {
			const colour = data.days_overdue > 60 ? "var(--red-500)" : "var(--orange-500)";
			value = `<span style="color: ${colour}">${value}</span>`;
		}
		return value;
	},
};
