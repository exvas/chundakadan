// Copyright (c) 2026, Chundakadan and contributors
// For license information, please see license.txt
frappe.query_reports["Account Ledger Report"] = {
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
            fieldname: "account",
            label: __("Account"),
            fieldtype: "Link",
            options: "Account",
            reqd: 1,
            get_query: () => {
                return {
                    filters: {
                        company: frappe.query_report.get_filter_value("company"),
                        is_group: 0,
                    },
                };
            },
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            reqd: 1,
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1,
        },
    ],
    // Bold the Opening / Closing Balance rows.
    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (data && (data.narration === __("Opening Balance") || data.narration === __("Closing Balance"))) {
            value = `<b>${value}</b>`;
        }
        return value;
    },
};
