// Copyright (c) 2025, Ashkar and contributors
// For license information, please see license.txt

frappe.query_reports["Monthly Sales Report"] = {
    "filters": [
        {
            fieldname: "year",
            label: __("Year"),
            fieldtype: "Int",
            default: new Date().getFullYear(),
            reqd: 1
        },
        {
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "Link",
            options: "Customer"
        },
        {
            fieldname: "district",
            label: __("District"),
            fieldtype: "Link",
            options: "Territory"
        },
        {
            fieldname: "sales_executive",
            label: __("Sales Executive"),
            fieldtype: "Data"
        }
    ]
};
