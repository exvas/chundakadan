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
	
	// Filter employees with pending encashment (exclude total/summary rows)
	let eligible_employees = data.filter(row => 
		row.pending_encashment_leaves > 0 && 
		row.total_payable_amount > 0 &&
		row.employee &&  // Must have employee ID
		!row.employee.toLowerCase().includes('total')  // Exclude total rows
	);
	
	if (eligible_employees.length === 0) {
		frappe.msgprint(__('No employees with pending leave encashment found.'));
		return;
	}
	
	// Calculate totals - group by employee to avoid counting same employee multiple times
	let employee_totals = {};
	eligible_employees.forEach(row => {
		// Skip if no valid employee ID
		if (!row.employee || typeof row.employee !== 'string') {
			return;
		}
		
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
	
	// Build employee breakdown for clarity
	let employee_breakdown = {};
	unique_employees.forEach(e => {
		if (!employee_breakdown[e.employee]) {
			employee_breakdown[e.employee] = {
				name: e.employee_name,
				leave_types: []
			};
		}
		employee_breakdown[e.employee].leave_types.push(e.leave_type);
	});
	
	let breakdown_html = Object.keys(employee_breakdown).map(emp => {
		let info = employee_breakdown[emp];
		return `<li>${info.name} (${emp}): ${info.leave_types.join(', ')}</li>`;
	}).join('');
	
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
				<td><strong>Total Leave Type Entries:</strong></td>
				<td>${unique_employees.length}</td>
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
		<div style="margin-bottom: 15px;">
			<strong>Employee Breakdown:</strong>
			<ul style="max-height: 200px; overflow-y: auto; margin-top: 5px;">
				${breakdown_html}
			</ul>
		</div>
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


// Selective create Additional Salary for chosen employees
function selective_create_additional_salary(report) {
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
	
	// Filter employees with pending encashment (exclude total/summary rows)
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
	
	// Build selection options grouped by employee
	let employee_options = {};
	eligible_employees.forEach(row => {
		if (!employee_options[row.employee]) {
			employee_options[row.employee] = {
				employee: row.employee,
				employee_name: row.employee_name || row.employee,
				company: row.company || '',
				leave_types: []
			};
		}
		employee_options[row.employee].leave_types.push({
			leave_type: row.leave_type,
			pending_leaves: row.pending_encashment_leaves,
			amount: row.total_payable_amount,
			basic_salary: row.basic_salary,
			per_day_rate: row.per_day_rate
		});
	});
	
	// Create selection dialog with attractive UI
	show_selection_dialog(employee_options, salary_component);
}

function show_selection_dialog(employee_options, salary_component) {
	// Build HTML for employee selection with checkboxes
	let employees_list = Object.values(employee_options);
	
	let html = `
		<div style="max-height: 600px; overflow-y: auto;">
			<style>
				.employee-card {
					border: 1px solid #e0e0e0;
					border-radius: 6px;
					padding: 10px 12px;
					margin-bottom: 8px;
					background: #fafafa;
					transition: all 0.2s ease;
				}
				.employee-card:hover {
					box-shadow: 0 2px 6px rgba(0,0,0,0.08);
					background: #ffffff;
					border-color: #3498db;
				}
				.employee-header {
					display: flex;
					align-items: center;
					gap: 10px;
				}
				.employee-checkbox {
					margin: 0;
					transform: scale(1.2);
					cursor: pointer;
					flex-shrink: 0;
				}
				.employee-info {
					flex: 1;
					min-width: 0;
				}
				.employee-name {
					font-size: 14px;
					font-weight: 600;
					color: #2c3e50;
					white-space: nowrap;
					overflow: hidden;
					text-overflow: ellipsis;
				}
				.employee-id {
					font-size: 11px;
					color: #7f8c8d;
				}
				.leave-type-list {
					display: grid;
					grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
					gap: 6px;
					margin-top: 8px;
					margin-left: 28px;
				}
				.leave-type-item {
					display: flex;
					align-items: center;
					padding: 6px 10px;
					background: white;
					border-radius: 4px;
					border: 1px solid #e8e8e8;
					gap: 8px;
				}
				.leave-type-item:hover {
					border-color: #3498db;
					background: #f0f8ff;
				}
				.leave-type-checkbox {
					margin: 0;
					transform: scale(1.1);
					cursor: pointer;
					flex-shrink: 0;
				}
				.leave-type-details {
					flex: 1;
					display: flex;
					justify-content: space-between;
					align-items: center;
					gap: 10px;
					min-width: 0;
				}
				.leave-type-name {
					font-weight: 500;
					color: #34495e;
					font-size: 13px;
					white-space: nowrap;
					overflow: hidden;
					text-overflow: ellipsis;
				}
				.leave-stats {
					display: flex;
					gap: 10px;
					font-size: 12px;
					flex-shrink: 0;
				}
				.stat-item {
					white-space: nowrap;
				}
				.stat-label {
					color: #95a5a6;
					font-size: 10px;
				}
				.stat-value {
					color: #2c3e50;
					font-weight: 600;
					margin-left: 3px;
				}
				.stat-value.amount {
					color: #27ae60;
				}
				.selection-summary {
					position: sticky;
					top: 0;
					background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
					color: white;
					padding: 12px 15px;
					border-radius: 6px;
					margin-bottom: 12px;
					box-shadow: 0 3px 6px rgba(0,0,0,0.15);
					z-index: 10;
				}
				.summary-title {
					font-size: 15px;
					font-weight: 600;
					margin-bottom: 8px;
					display: flex;
					align-items: center;
					gap: 8px;
				}
				.summary-grid {
					display: grid;
					grid-template-columns: repeat(3, 1fr);
					gap: 12px;
				}
				.summary-item {
					text-align: center;
					background: rgba(255,255,255,0.15);
					padding: 8px;
					border-radius: 4px;
				}
				.summary-value {
					font-size: 20px;
					font-weight: 700;
					display: block;
					line-height: 1.2;
				}
				.summary-label {
					font-size: 11px;
					opacity: 0.95;
					text-transform: uppercase;
					letter-spacing: 0.5px;
					margin-top: 2px;
					display: block;
				}
				.select-all-section {
					background: #e3f2fd;
					padding: 10px 12px;
					border-radius: 5px;
					margin-bottom: 10px;
					display: flex;
					align-items: center;
					border: 1px solid #90caf9;
				}
				.select-all-checkbox {
					margin: 0 10px 0 0;
					transform: scale(1.3);
					cursor: pointer;
				}
				.select-all-label {
					font-weight: 600;
					color: #1976d2;
					cursor: pointer;
					font-size: 14px;
				}
				.employees-container {
					display: grid;
					gap: 8px;
				}
			</style>
			
			<div class="selection-summary">
				<div class="summary-title">
					<span>📋</span>
					<span>Selection Summary</span>
				</div>
				<div class="summary-grid">
					<div class="summary-item">
						<span class="summary-value" id="selected-employees-count">0</span>
						<span class="summary-label">Employees</span>
					</div>
					<div class="summary-item">
						<span class="summary-value" id="selected-leaves-count">0.00</span>
						<span class="summary-label">Leaves</span>
					</div>
					<div class="summary-item">
						<span class="summary-value" id="selected-amount-total">₹ 0.00</span>
						<span class="summary-label">Total Amount</span>
					</div>
				</div>
			</div>
			
			<div class="select-all-section">
				<input type="checkbox" class="select-all-checkbox" id="select-all-employees">
				<label class="select-all-label" for="select-all-employees">
					Select All (${employees_list.length} employees)
				</label>
			</div>
			
			<div class="employees-container">
	`;
	
	employees_list.forEach((emp, emp_idx) => {
		html += `
			<div class="employee-card">
				<div class="employee-header">
					<input type="checkbox" class="employee-checkbox" 
						data-employee="${emp.employee}" 
						id="emp-${emp_idx}">
					<div class="employee-info">
						<div class="employee-name" title="${emp.employee_name}">${emp.employee_name}</div>
						<div class="employee-id">${emp.employee}</div>
					</div>
				</div>
				<div class="leave-type-list">
		`;
		
		emp.leave_types.forEach((lt, lt_idx) => {
			html += `
				<div class="leave-type-item">
					<input type="checkbox" class="leave-type-checkbox" 
						data-employee="${emp.employee}"
						data-employee-name="${emp.employee_name}"
						data-company="${emp.company}"
						data-leave-type="${lt.leave_type}"
						data-pending-leaves="${lt.pending_leaves}"
						data-amount="${lt.amount}"
						id="lt-${emp_idx}-${lt_idx}">
					<div class="leave-type-details">
						<span class="leave-type-name" title="${lt.leave_type}">${lt.leave_type}</span>
						<div class="leave-stats">
							<span class="stat-item">
								<span class="stat-label">Leaves:</span>
								<span class="stat-value">${lt.pending_leaves.toFixed(1)}</span>
							</span>
							<span class="stat-item">
								<span class="stat-label">Amt:</span>
								<span class="stat-value amount">${format_currency(lt.amount, null, 0)}</span>
							</span>
						</div>
					</div>
				</div>
			`;
		});
		
		html += `
				</div>
			</div>
		`;
	});
	
	html += '</div></div>';
	
	// Create dialog
	let d = new frappe.ui.Dialog({
		title: __('Select Employees for Additional Salary'),
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'employee_selection',
				options: html
			},
			{
				fieldtype: 'Section Break'
			},
			{
				fieldtype: 'Date',
				fieldname: 'payroll_date',
				label: __('Payroll Date'),
				reqd: 1,
				default: frappe.datetime.get_today(),
				description: __('This date will be used for all Additional Salary entries')
			},
			{
				fieldtype: 'Check',
				fieldname: 'overwrite_salary_structure_amount',
				label: __('Overwrite Salary Structure Amount'),
				default: 1
			}
		],
		size: 'extra-large',
		primary_action_label: __('Create Selected'),
		primary_action: function(values) {
			// Get selected leave types
			let selected = [];
			d.$wrapper.find('.leave-type-checkbox:checked').each(function() {
				let $checkbox = $(this);
				selected.push({
					employee: $checkbox.data('employee'),
					employee_name: $checkbox.data('employee-name'),
					company: $checkbox.data('company'),
					leave_type: $checkbox.data('leave-type'),
					pending_leaves: parseFloat($checkbox.data('pending-leaves')),
					amount: parseFloat($checkbox.data('amount'))
				});
			});
			
			if (selected.length === 0) {
				frappe.msgprint(__('Please select at least one leave type to create Additional Salary'));
				return;
			}
			
			// Call bulk creation method
			frappe.call({
				method: 'chundakadan.chundakadan.report.leave_encashment_balance.leave_encashment_balance.bulk_create_additional_salary',
				args: {
					employees_data: selected,
					salary_component: salary_component,
					payroll_date: values.payroll_date,
					overwrite_salary_structure_amount: values.overwrite_salary_structure_amount
				},
				freeze: true,
				freeze_message: __('Creating Additional Salary entries...'),
				callback: function(r) {
					if (r.message) {
						let result = r.message;
						
						// Show detailed results
						let result_message = `
							<div style="margin-bottom: 15px;">
								<h4>✅ Creation Results</h4>
							</div>
							<table class="table table-bordered">
								<tr class="success">
									<td><strong>Successfully Created:</strong></td>
									<td><strong>${result.created}</strong></td>
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
									<h5>⚠️ Errors:</h5>
									<ul style="max-height: 300px; overflow-y: auto;">
										${result.errors.map(err => `<li>${err}</li>`).join('')}
									</ul>
								</div>
							`;
						}
						
						if (result.created_docs && result.created_docs.length > 0) {
							result_message += `
								<div style="margin-top: 15px;">
									<h5>📄 Created Documents:</h5>
									<ul style="max-height: 200px; overflow-y: auto;">
										${result.created_docs.map(doc => `<li><a href="/app/additional-salary/${doc}" target="_blank">${doc}</a></li>`).join('')}
									</ul>
								</div>
							`;
						}
						
						frappe.msgprint({
							title: __('Creation Complete'),
							message: result_message,
							indicator: result.failed > 0 ? 'orange' : 'green',
							wide: true
						});
						
						// Close dialog and refresh report
						d.hide();
						frappe.query_report.refresh();
					}
				},
				error: function(r) {
					console.error('Selective creation error:', r);
					frappe.msgprint({
						title: __('Error'),
						message: __('An error occurred during creation. Check console for details.'),
						indicator: 'red'
					});
				}
			});
		}
	});
	
	d.show();
	
	// Add event listeners after dialog is shown
	setTimeout(() => {
		// Update summary on checkbox change
		function updateSummary() {
			let selected_employees = new Set();
			let total_leaves = 0;
			let total_amount = 0;
			
			d.$wrapper.find('.leave-type-checkbox:checked').each(function() {
				let $checkbox = $(this);
				selected_employees.add($checkbox.data('employee'));
				total_leaves += parseFloat($checkbox.data('pending-leaves'));
				total_amount += parseFloat($checkbox.data('amount'));
			});
			
			d.$wrapper.find('#selected-employees-count').text(selected_employees.size);
			d.$wrapper.find('#selected-leaves-count').text(total_leaves.toFixed(2));
			d.$wrapper.find('#selected-amount-total').text(format_currency(total_amount, null, 0));
		}
		
		// Employee checkbox - select/deselect all leave types for that employee
		d.$wrapper.find('.employee-checkbox').on('change', function() {
			let employee = $(this).data('employee');
			let is_checked = $(this).prop('checked');
			d.$wrapper.find(`.leave-type-checkbox[data-employee="${employee}"]`).prop('checked', is_checked);
			updateSummary();
		});
		
		// Leave type checkbox - update employee checkbox state
		d.$wrapper.find('.leave-type-checkbox').on('change', function() {
			let employee = $(this).data('employee');
			let all_checked = true;
			let any_checked = false;
			
			d.$wrapper.find(`.leave-type-checkbox[data-employee="${employee}"]`).each(function() {
				if ($(this).prop('checked')) {
					any_checked = true;
				} else {
					all_checked = false;
				}
			});
			
			let $emp_checkbox = d.$wrapper.find(`.employee-checkbox[data-employee="${employee}"]`);
			$emp_checkbox.prop('checked', all_checked);
			$emp_checkbox.prop('indeterminate', any_checked && !all_checked);
			
			updateSummary();
		});
		
		// Select all checkbox
		d.$wrapper.find('#select-all-employees').on('change', function() {
			let is_checked = $(this).prop('checked');
			d.$wrapper.find('.employee-checkbox, .leave-type-checkbox').prop('checked', is_checked);
			updateSummary();
		});
		
		// Initialize summary
		updateSummary();
	}, 100);
}
