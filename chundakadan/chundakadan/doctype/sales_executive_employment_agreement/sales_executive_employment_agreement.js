// Copyright (c) 2025, TBO Cloud and contributors
// For license information, please see license.txt

frappe.ui.form.on('Sales Executive Employment Agreement', {
	refresh: function(frm) {
		// Set default roles and responsibilities if empty
		if (!frm.doc.roles_and_responsibilities && frm.doc.docstatus === 0) {
			frappe.call({
				method: 'chundakadan.chundakadan.doctype.sales_executive_employment_agreement.sales_executive_employment_agreement.get_default_roles_and_responsibilities',
				callback: function(r) {
					if (r.message) {
						frm.set_value('roles_and_responsibilities', r.message);
					}
				}
			});
		}
		
		// Add custom buttons based on status
		if (frm.doc.docstatus === 1) {
			// Add button to view performance summary
			frm.add_custom_button(__('View Performance Summary'), function() {
				frappe.call({
					method: 'get_performance_summary',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint({
								title: __('Performance Summary'),
								message: `<pre>${JSON.stringify(r.message, null, 2)}</pre>`,
								indicator: 'blue'
							});
						}
					}
				});
			});
			
			// Add button to terminate agreement
			if (frm.doc.status === 'Active') {
				frm.add_custom_button(__('Terminate Agreement'), function() {
					frappe.confirm(
						'Are you sure you want to terminate this agreement?',
						function() {
							frappe.call({
								method: 'frappe.client.set_value',
								args: {
									doctype: 'Sales Executive Employment Agreement',
									name: frm.doc.name,
									fieldname: 'status',
									value: 'Terminated'
								},
								callback: function(r) {
									frm.reload_doc();
								}
							});
						}
					);
				}, __('Actions'));
			}
		}
		
		// Color code based on status
		if (frm.doc.status) {
			let color_map = {
				'Draft': 'gray',
				'Active': 'green',
				'Completed': 'blue',
				'Terminated': 'red',
				'Cancelled': 'red'
			};
			frm.set_indicator_color(color_map[frm.doc.status] || 'gray');
		}
		
		// Show warning for targets
		if (frm.doc.docstatus === 0) {
			show_target_warnings(frm);
		}
	},
	
	employee_name: function(frm) {
		// Auto-populate employee address if employee is linked
		if (frm.doc.employee_name) {
			frappe.db.get_value('Employee', frm.doc.employee_name, ['permanent_address', 'current_address'], function(r) {
				if (r) {
					frm.set_value('employee_address', r.permanent_address || r.current_address);
				}
			});
		}
	},
	
	cash_collection_amount: function(frm) {
		validate_cash_target(frm);
	},
	
	sales_target_penalty_70: function(frm) {
		validate_sales_target(frm);
	},
	
	start_date: function(frm) {
		if (frm.doc.start_date && !frm.doc.end_date) {
			// Auto-set end date to 1 year from start date
			let end_date = frappe.datetime.add_days(frm.doc.start_date, 365);
			frm.set_value('end_date', end_date);
		}
	}
});

function show_target_warnings(frm) {
	let warnings = [];
	
	if (!frm.doc.cash_collection_amount || frm.doc.cash_collection_amount < 1500000) {
		warnings.push('Cash collection target should be at least INR 15,00,000 (Fifteen Lakhs)');
	}
	
	if (!frm.doc.sales_target_penalty_70 || frm.doc.sales_target_penalty_70 < 70) {
		warnings.push('Sales target percentage should be at least 70%');
	}
	
	if (!frm.doc.min_new_leads_per_month || frm.doc.min_new_leads_per_month < 3) {
		warnings.push('Minimum new leads per month should be at least 3');
	}
	
	if (!frm.doc.min_demos_per_month || frm.doc.min_demos_per_month < 4) {
		warnings.push('Minimum demos per month should be at least 4');
	}
	
	if (warnings.length > 0) {
		frappe.msgprint({
			title: __('Target Recommendations'),
			message: warnings.join('<br>'),
			indicator: 'orange'
		});
	}
}

function validate_cash_target(frm) {
	if (frm.doc.cash_collection_amount) {
		if (frm.doc.cash_collection_amount < 0) {
			frappe.msgprint(__('Cash collection target cannot be negative'));
			frm.set_value('cash_collection_amount', 1500000);
		} else if (frm.doc.cash_collection_amount < 1500000) {
			frappe.msgprint({
				title: __('Warning'),
				message: __('Standard cash collection target is INR 15,00,000 (Fifteen Lakhs)'),
				indicator: 'orange'
			});
		}
	}
}

function validate_sales_target(frm) {
	if (frm.doc.sales_target_penalty_70) {
		if (frm.doc.sales_target_penalty_70 < 0 || frm.doc.sales_target_penalty_70 > 100) {
			frappe.msgprint(__('Sales target percentage must be between 0 and 100'));
			frm.set_value('sales_target_penalty_70', 70);
		} else if (frm.doc.sales_target_penalty_70 < 70) {
			frappe.msgprint({
				title: __('Warning'),
				message: __('Standard minimum sales target is 70%'),
				indicator: 'orange'
			});
		}
	}
}

// Format currency display
frappe.ui.form.on('Sales Executive Employment Agreement', {
	onload: function(frm) {
		frm.set_query('employee_name', function() {
			return {
				filters: {
					'status': 'Active'
				}
			};
		});
	}
});
