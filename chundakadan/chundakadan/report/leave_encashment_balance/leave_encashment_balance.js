// Copyright (c) 2024, Chundakadan and contributors
// For license information, please see license.txt

frappe.query_reports["Leave Encashment Balance"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 0
		},
		{
			"fieldname": "leave_period",
			"label": __("Leave Period"),
			"fieldtype": "Link",
			"options": "Leave Period",
			"reqd": 1
		},
		{
			"fieldname": "department",
			"label": __("Department"),
			"fieldtype": "Link",
			"options": "Department",
			"reqd": 0
		},
		{
			"fieldname": "employee",
			"label": __("Employee"),
			"fieldtype": "Link",
			"options": "Employee",
			"reqd": 0
		},
		{
			"fieldname": "leave_type",
			"label": __("Leave Type"),
			"fieldtype": "Link",
			"options": "Leave Type",
			"get_query": function() {
				return {
					"filters": {
						"allow_encashment": 1
					}
				};
			},
			"reqd": 0
		},
		{
			"fieldname": "payment_days",
			"label": __("Payment Days"),
			"fieldtype": "Int",
			"default": 30,
			"reqd": 1
		},
		{
			"fieldname": "salary_component",
			"label": __("Leave Encashment Salary Component"),
			"fieldtype": "Link",
			"options": "Salary Component",
			"get_query": function() {
				return {
					"filters": {
						"type": "Earning"
					}
				};
			},
			"reqd": 0
		}
	],
	
	"onload": function(report) {
		// Add bulk create button
		report.page.add_inner_button(__("Bulk Create Additional Salary"), function() {
			bulk_create_additional_salary(report);
		});
	},
	
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		
		if (column.fieldname == "pending_encashment_leaves" && data && data.pending_encashment_leaves > 0) {
			value = "<span style='color:orange; font-weight:bold'>" + value + "</span>";
		}
		
		if (column.fieldname == "total_payable_amount" && data && data.total_payable_amount > 0) {
			value = "<span style='color:green; font-weight:bold'>" + value + "</span>";
		}
		
		return value;
	}
};

// Bulk create Additional Salary for all employees
function bulk_create_additional_salary(report) {
	// Get salary component from filters
	let salary_component = frappe.query_report.get_filter_value('salary_component');
	
	if (!salary_component) {
		frappe.msgprint({
			title: __('Salary Component Required'),
			message: __('Please select a Leave Encashment Salary Component in the filters before creating Additional Salary'),
			indicator: 'red'
		});
		return;
	}
	
	// Get report data
	let data = frappe.query_report.data;
	
	if (!data || data.length === 0) {
		frappe.msgprint(__('No data available. Please run the report first.'));
		return;
	}
	
	// Filter employees with pending encashment
	let eligible_employees = data.filter(row => row.pending_encashment_leaves > 0 && row.total_payable_amount > 0);
	
	if (eligible_employees.length === 0) {
		frappe.msgprint(__('No employees with pending leave encashment found.'));
		return;
	}
	
	// Calculate totals - group by employee to avoid counting same employee multiple times
	let employee_totals = {};
	eligible_employees.forEach(row => {
		let key = row.employee + '|' + row.leave_type;
		if (!employee_totals[key]) {
			employee_totals[key] = {
				employee: row.employee,
				employee_name: row.employee_name,
				leave_type: row.leave_type,
				pending_leaves: row.pending_encashment_leaves,
				amount: row.total_payable_amount
			};
		}
	});
	
	let unique_employees = Object.values(employee_totals);
	let total_employees = new Set(unique_employees.map(e => e.employee)).size;
	let total_amount = unique_employees.reduce((sum, e) => sum + e.amount, 0);
	let total_leaves = unique_employees.reduce((sum, e) => sum + e.pending_leaves, 0);
	
	// Show confirmation with summary
	let message = `
		<div style="margin-bottom: 15px;">
			<h4>Bulk Create Additional Salary</h4>
			<p>This will create Additional Salary entries for all eligible employees.</p>
		</div>
		<table class="table table-bordered" style="margin-bottom: 15px;">
			<tr>
				<td><strong>Total Employees:</strong></td>
				<td>${total_employees}</td>
			</tr>
			<tr>
				<td><strong>Total Leave Entries:</strong></td>
				<td>${unique_employees.length} (${total_employees} employee(s) × leave types)</td>
			</tr>
			<tr>
				<td><strong>Total Leaves:</strong></td>
				<td>${total_leaves.toFixed(2)}</td>
			</tr>
			<tr>
				<td><strong>Total Amount:</strong></td>
				<td>${format_currency(total_amount)}</td>
			</tr>
			<tr>
				<td><strong>Salary Component:</strong></td>
				<td>${salary_component}</td>
			</tr>
		</table>
		<p style="color: #856404; background-color: #fff3cd; padding: 10px; border-radius: 4px;">
			<strong>Note:</strong> Existing Additional Salary entries for the same employee and payroll date will be skipped.
		</p>
	`;
	
	frappe.confirm(
		message,
		function() {
			// Get payroll date
			frappe.prompt([
				{
					'fieldname': 'payroll_date',
					'fieldtype': 'Date',
					'label': __('Payroll Date'),
					'reqd': 1,
					'default': frappe.datetime.get_today(),
					'description': __('This date will be used for all Additional Salary entries')
				},
				{
					'fieldname': 'overwrite_salary_structure_amount',
					'fieldtype': 'Check',
					'label': __('Overwrite Salary Structure Amount'),
					'default': 1
				}
			],
			function(values) {
				// Prepare employee data - use unique entries
				let employees_data = unique_employees.map(e => ({
					employee: e.employee,
					employee_name: e.employee_name,
					leave_type: e.leave_type,
					pending_leaves: e.pending_leaves,
					amount: e.amount,
					company: eligible_employees.find(row => row.employee === e.employee && row.leave_type === e.leave_type).company || ''
				}));
				
				// Debug: Log the data being sent
				console.log('Sending employees_data:', employees_data);
				
				// Call bulk creation method
				frappe.call({
					method: 'chundakadan.chundakadan.report.leave_encashment_balance.leave_encashment_balance.bulk_create_additional_salary',
					args: {
						employees_data: employees_data,
						salary_component: salary_component,
						payroll_date: values.payroll_date,
						overwrite_salary_structure_amount: values.overwrite_salary_structure_amount
					},
					freeze: true,
					freeze_message: __('Creating Additional Salary entries...'),
					callback: function(r) {
						if (r.message) {
							let result = r.message;
							
							// Debug: Log the result
							console.log('Bulk creation result:', result);
							
							// Show detailed results
							let result_message = `
								<div style="margin-bottom: 15px;">
									<h4>Bulk Creation Results</h4>
								</div>
								<table class="table table-bordered">
									<tr class="success">
										<td><strong>Successfully Created:</strong></td>
										<td>${result.created}</td>
									</tr>
									<tr class="warning">
										<td><strong>Skipped (Already Exists):</strong></td>
										<td>${result.skipped}</td>
									</tr>
									<tr class="danger">
										<td><strong>Failed:</strong></td>
										<td>${result.failed}</td>
									</tr>
									<tr>
										<td><strong>Total Processed:</strong></td>
										<td>${result.total}</td>
									</tr>
								</table>
							`;
							
							if (result.errors && result.errors.length > 0) {
								result_message += `
									<div style="margin-top: 15px;">
										<h5>Errors:</h5>
										<ul style="max-height: 300px; overflow-y: auto;">
											${result.errors.map(err => `<li>${err}</li>`).join('')}
										</ul>
									</div>
								`;
							}
							
							if (result.created_docs && result.created_docs.length > 0) {
								result_message += `
									<div style="margin-top: 15px;">
										<h5>Created Documents:</h5>
										<ul style="max-height: 200px; overflow-y: auto;">
											${result.created_docs.map(doc => `<li><a href="/app/additional-salary/${doc}" target="_blank">${doc}</a></li>`).join('')}
										</ul>
									</div>
								`;
							}
							
							frappe.msgprint({
								title: __('Bulk Creation Complete'),
								message: result_message,
								indicator: result.failed > 0 ? 'orange' : 'green',
								wide: true
							});
							
							// Refresh report
							frappe.query_report.refresh();
						}
					},
					error: function(r) {
						console.error('Bulk creation error:', r);
						frappe.msgprint({
							title: __('Error'),
							message: __('An error occurred during bulk creation. Check console for details.'),
							indicator: 'red'
						});
					}
				});
			},
			__('Payroll Date'),
			__('Create All')
			);
		}
	);
}
