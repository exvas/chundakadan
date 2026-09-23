// Copyright (c) 2026, Chundakadan and contributors
frappe.query_reports["Stock Count"] = {
	filters: [
		{
			fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company",
			default: frappe.defaults.get_user_default("Company"), reqd: 1,
		},
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{
			fieldname: "group_by", label: __("Group By"), fieldtype: "Select",
			options: ["Item and Warehouse", "Item"], default: "Item and Warehouse",
		},
		{ fieldname: "warehouse", label: __("Warehouse"), fieldtype: "Link", options: "Warehouse" },
		{ fieldname: "item_code", label: __("Item"), fieldtype: "Link", options: "Item" },
		{ fieldname: "brand", label: __("Brand"), fieldtype: "Link", options: "Brand" },
		{ fieldname: "item_group", label: __("Item Group"), fieldtype: "Link", options: "Item Group" },
		{ fieldname: "hide_zero_balance", label: __("Hide Zero Balance"), fieldtype: "Check", default: 1 },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "balance_qty" && data && data.balance_qty < 0) {
			value = `<span style="color: var(--red-500)">${value}</span>`;
		}
		return value;
	},
};
