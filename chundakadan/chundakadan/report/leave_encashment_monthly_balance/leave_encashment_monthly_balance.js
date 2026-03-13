// Copyright (c) 2024, Chundakadan and contributors
// For license information, please see license.txt

frappe.query_reports["Leave Encashment Monthly Balance"] = {
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
			"fieldname": "employee",
			"label": __("Employee"),
			"fieldtype": "Link",
			"options": "Employee",
			"reqd": 1,
			"on_change": function() {
				let employee = frappe.query_report.get_filter_value('employee');
				if (employee) {
					frappe.db.get_value('Employee', employee, 'relieving_date', (r) => {
						if (r && r.relieving_date) {
							frappe.query_report.set_filter_value('to_date', r.relieving_date);
						} else {
							frappe.query_report.set_filter_value('to_date', frappe.datetime.get_today());
						}
					});
				}
			}
		},
		{
			"fieldname": "leave_period",
			"label": __("Leave Period"),
			"fieldtype": "Link",
			"options": "Leave Period",
			"reqd": 0
		},
		{
			"fieldname": "to_date",
			"label": __("Reference Date (Relieving Date)"),
			"fieldtype": "Date",
			"reqd": 0
		},
		{
			"fieldname": "department",
			"label": __("Department"),
			"fieldtype": "Link",
			"options": "Department",
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
		
		// Add selective create button
		report.page.add_inner_button(__("Create Individual Additional Salary"), function() {
			selective_create_additional_salary(report);
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
	let eligible_employees = data.filter(row => 
		row.pending_encashment_leaves > 0 && 
		row.total_payable_amount > 0 &&
		row.employee &&
		!row.employee.toLowerCase().includes('total')
	);
	
	if (eligible_employees.length === 0) {
		frappe.msgprint(__('No employees with pending leave encashment found.'));
		return;
	}
	
	// Calculate totals
	let employee_totals = {};
	eligible_employees.forEach(row => {
		if (!row.employee || typeof row.employee !== 'string') return;
		
		let key = row.employee + '|' + row.leave_type;
		if (!employee_totals[key]) {
			employee_totals[key] = {
				employee: row.employee,
				employee_name: row.employee_name || row.employee,
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
	
	// Confirmation UI
	let breakdown_html = Object.keys(employee_totals).map(key => {
		let e = employee_totals[key];
		return `<li>${e.employee_name} (${e.employee}): ${e.leave_type}</li>`;
	}).join('');
	
	let message = `
		<div style="margin-bottom: 15px;">
			<h4>Bulk Create Additional Salary</h4>
			<p>This will create Additional Salary entries for all eligible employees.</p>
		</div>
		<table class="table table-bordered" style="margin-bottom: 15px;">
			<tr><td><strong>Total Employees:</strong></td><td>${total_employees}</td></tr>
			<tr><td><strong>Total Entries:</strong></td><td>${unique_employees.length}</td></tr>
			<tr><td><strong>Total Leaves:</strong></td><td>${total_leaves.toFixed(2)}</td></tr>
			<tr><td><strong>Total Amount:</strong></td><td>${format_currency(total_amount)}</td></tr>
			<tr><td><strong>Salary Component:</strong></td><td>${salary_component}</td></tr>
		</table>
		<div style="margin-bottom: 15px;">
			<strong>Entries:</strong>
			<ul style="max-height: 200px; overflow-y: auto; margin-top: 5px;">${breakdown_html}</ul>
		</div>
	`;
	
	frappe.confirm(message, function() {
		frappe.prompt([
			{
				'fieldname': 'payroll_date',
				'fieldtype': 'Date',
				'label': __('Payroll Date'),
				'reqd': 1,
				'default': frappe.datetime.get_today()
			}
		], function(values) {
			let employees_data = unique_employees.map(e => ({
				employee: e.employee,
				employee_name: e.employee_name,
				leave_type: e.leave_type,
				pending_leaves: e.pending_leaves,
				amount: e.amount,
				company: eligible_employees.find(row => row.employee === e.employee && row.leave_type === e.leave_type).company || ''
			}));
			
			frappe.call({
				method: 'chundakadan.chundakadan.report.leave_encashment_monthly_balance.leave_encashment_monthly_balance.bulk_create_additional_salary',
				args: {
					employees_data: employees_data,
					salary_component: salary_component,
					payroll_date: values.payroll_date,
					overwrite_salary_structure_amount: 0
				},
				freeze: true,
				freeze_message: __('Creating Additional Salary entries...'),
				callback: function(r) {
					if (r.message) {
						let result = r.message;
						let result_message = `
							<h4>Bulk Creation Results</h4>
							<table class="table table-bordered">
								<tr class="success"><td><strong>Created:</strong></td><td>${result.created}</td></tr>
								<tr class="warning"><td><strong>Skipped:</strong></td><td>${result.skipped}</td></tr>
								<tr class="danger"><td><strong>Failed:</strong></td><td>${result.failed}</td></tr>
							</table>
						`;
						frappe.msgprint({ title: __('Complete'), message: result_message, wide: true });
						frappe.query_report.refresh();
					}
				}
			});
		});
	});
}

// Selective create Additional Salary
function selective_create_additional_salary(report) {
	let salary_component = frappe.query_report.get_filter_value('salary_component');
	if (!salary_component) {
		frappe.msgprint(__('Please select a Salary Component'));
		return;
	}
	
	let data = frappe.query_report.data;
	let eligible_employees = data.filter(row => 
		row.pending_encashment_leaves > 0 && row.total_payable_amount > 0 && row.employee && !row.employee.toLowerCase().includes('total')
	);
	
	if (eligible_employees.length === 0) {
		frappe.msgprint(__('No eligible employees found'));
		return;
	}
	
	let employee_options = {};
	eligible_employees.forEach(row => {
		if (!employee_options[row.employee]) {
			employee_options[row.employee] = {
				employee: row.employee,
				employee_name: row.employee_name,
				company: row.company || '',
				leave_types: []
			};
		}
		employee_options[row.employee].leave_types.push(row);
	});
	
	show_selection_dialog(employee_options, salary_component);
}

function show_selection_dialog(employee_options, salary_component) {
	let employees_list = Object.values(employee_options);
	let html = `
		<div style="max-height: 500px; overflow-y: auto;">
			<div id="selection-summary" style="background: #eee; padding: 10px; margin-bottom: 10px; border-radius: 4px;">
				Selected: <span id="selected-count">0</span> | Amount: <span id="selected-amount">0</span>
			</div>
			<div class="list-group">
	`;
	
	employees_list.forEach((emp, e_idx) => {
		html += `<div class="list-group-item">
			<h5 class="mb-1"><input type="checkbox" class="employee-checkbox" data-employee="${emp.employee}"> ${emp.employee_name}</h5>
			<div style="margin-left: 20px;">
		`;
		emp.leave_types.forEach((lt, l_idx) => {
			html += `
				<div class="form-check">
					<input class="form-check-input leave-type-checkbox" type="checkbox" 
						data-employee="${emp.employee}" data-leave-type="${lt.leave_type}" 
						data-amount="${lt.total_payable_amount}" data-leaves="${lt.pending_encashment_leaves}"
						data-company="${emp.company}" data-name="${emp.employee_name}">
					<label class="form-check-label">${lt.leave_type} (${lt.pending_encashment_leaves} days @ ${format_currency(lt.total_payable_amount)})</label>
				</div>
			`;
		});
		html += `</div></div>`;
	});
	html += `</div></div>`;

	let d = new frappe.ui.Dialog({
		title: __('Select for Additional Salary'),
		fields: [
			{ fieldtype: 'HTML', fieldname: 'selection_html', options: html },
			{ fieldtype: 'Date', fieldname: 'payroll_date', label: __('Payroll Date'), reqd: 1, default: frappe.datetime.get_today() }
		],
		size: 'large',
		primary_action_label: __('Create Selected'),
		primary_action: function(values) {
			let selected = [];
			d.$wrapper.find('.leave-type-checkbox:checked').each(function() {
				let $cb = $(this);
				selected.push({
					employee: $cb.data('employee'),
					employee_name: $cb.data('name'),
					company: $cb.data('company'),
					leave_type: $cb.data('leave-type'),
					pending_leaves: $cb.data('leaves'),
					amount: $cb.data('amount')
				});
			});
			
			if (selected.length === 0) return;
			
			frappe.call({
				method: 'chundakadan.chundakadan.report.leave_encashment_monthly_balance.leave_encashment_monthly_balance.bulk_create_additional_salary',
				args: {
					employees_data: selected,
					salary_component: salary_component,
					payroll_date: values.payroll_date
				},
				freeze: true,
				callback: function(r) {
					if (r.message) {
						frappe.msgprint(__('Created {0} entries', [r.message.created]));
						d.hide();
						frappe.query_report.refresh();
					}
				}
			});
		}
	});

	d.show();
	
	d.$wrapper.find('.employee-checkbox').on('change', function() {
		let emp = $(this).data('employee');
		d.$wrapper.find(`.leave-type-checkbox[data-employee="${emp}"]`).prop('checked', $(this).prop('checked'));
		update_summary();
	});

	d.$wrapper.find('.leave-type-checkbox').on('change', function() {
		update_summary();
	});

	function update_summary() {
		let count = 0;
		let amount = 0;
		d.$wrapper.find('.leave-type-checkbox:checked').each(function() {
			count++;
			amount += parseFloat($(this).data('amount'));
		});
		d.$wrapper.find('#selected-count').text(count);
		d.$wrapper.find('#selected-amount').text(format_currency(amount));
	}
}
