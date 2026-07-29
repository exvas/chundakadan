// Copyright (c) 2026, Ashkar and contributors
// For license information, please see license.txt

frappe.query_reports["Late Entry Deduction"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1,
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "shift",
			label: __("Shift"),
			fieldtype: "Link",
			options: "Shift Type",
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
	],

	onload: function (report) {
		report.page.add_inner_button(__("Create Additional Salary"), function () {
			const rows = (frappe.query_report.data || []).filter(
				(r) => r.employee && flt(r.deduction_amount) > 0
			);
			if (!rows.length) {
				frappe.msgprint(__("No late-entry deductions to post. Run the report first."));
				return;
			}
			const total = rows.reduce((s, r) => s + flt(r.deduction_amount), 0);
			frappe.confirm(
				__(
					"Create <b>{0}</b> DRAFT 'Late Arrival Deduction' Additional Salary entries totalling <b>{1}</b>?<br><small>Left as Draft — HR submits before running payroll. Re-running replaces existing drafts for the same month.</small>",
					[rows.length, format_currency(total)]
				),
				function () {
					frappe.call({
						method: "chundakadan.chundakadan.report.late_entry_deduction.late_entry_deduction.create_additional_salary",
						args: {
							rows: JSON.stringify(rows),
							from_date: frappe.query_report.get_filter_value("from_date"),
							to_date: frappe.query_report.get_filter_value("to_date"),
							company: frappe.query_report.get_filter_value("company"),
						},
						freeze: true,
						freeze_message: __("Creating Additional Salary entries..."),
						callback: function (r) {
							if (!r.message) return;
							const m = r.message;
							let html = `<table class="table table-bordered">
								<tr><td><b>Created</b></td><td>${m.created}</td></tr>
								<tr><td><b>Replaced (existing draft)</b></td><td>${m.replaced}</td></tr>
								<tr><td><b>Skipped</b></td><td>${m.skipped}</td></tr>
								<tr><td><b>Failed</b></td><td>${m.failed}</td></tr></table>`;
							if (m.errors && m.errors.length) {
								html += `<div class="text-muted small">${m.errors.join("<br>")}</div>`;
							}
							frappe.msgprint({ title: __("Additional Salary (Draft)"), message: html, wide: true });
						},
					});
				}
			);
		});
	},

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "deduction_amount" && data && flt(data.deduction_amount) > 0) {
			value = `<span style="color:#c0392b;font-weight:600">${value}</span>`;
		}
		return value;
	},
};
