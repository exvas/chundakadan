// Copyright (c) 2025, TBO Cloud and contributors
// For license information, please see license.txt

frappe.ui.form.on('Warning Letter', {
	refresh: function(frm) {
		// Set default subject if empty
		if (!frm.doc.subject && frm.doc.violation_type && frm.doc.warning_type) {
			frm.set_value('subject', get_default_subject(frm.doc.warning_type, frm.doc.violation_type));
		}
		
		// Add custom buttons based on status
		if (frm.doc.docstatus === 1) {
			// Show warning count
			if (frm.doc.employee) {
				frappe.call({
					method: 'chundakadan.chundakadan.doctype.warning_letter.warning_letter.get_employee_warning_count',
					args: {
						employee: frm.doc.employee
					},
					callback: function(r) {
						if (r.message) {
							frm.dashboard.add_indicator(__('Total Warnings: {0}', [r.message]), 
								r.message >= 3 ? 'red' : r.message >= 2 ? 'orange' : 'blue');
						}
					}
				});
			}
			
			// Add acknowledge button for employees
			if (frm.doc.status === 'Issued' && frm.doc.acknowledgment_required && !frm.doc.employee_signature_date) {
				frm.add_custom_button(__('Acknowledge Warning'), function() {
					frappe.call({
						method: 'acknowledge_warning',
						doc: frm.doc,
						callback: function(r) {
							frm.reload_doc();
						}
					});
				}).addClass('btn-primary');
			}
			
			// Send email button
			frm.add_custom_button(__('Send Email'), function() {
				frappe.call({
					method: 'frappe.core.doctype.communication.email.make',
					args: {
						recipients: frm.doc.employee,
						subject: frm.doc.subject,
						content: frm.doc.letter_content,
						doctype: frm.doc.doctype,
						name: frm.doc.name,
						send_email: 1
					},
					callback: function() {
						frappe.msgprint(__('Email sent successfully'));
					}
				});
			}, __('Actions'));
		}
		
		// Color code based on status
		if (frm.doc.status) {
			let color_map = {
				'Draft': 'gray',
				'Issued': 'orange',
				'Acknowledged': 'green',
				'Cancelled': 'red'
			};
			frm.set_df_property('status', 'color', color_map[frm.doc.status] || 'gray');
		}
		
		// Show warning history
		if (frm.doc.employee && frm.doc.docstatus === 0) {
			show_warning_history(frm);
		}
	},
	
	employee: function(frm) {
		if (frm.doc.employee) {
			// Fetch employee details
			frappe.db.get_value('Employee', frm.doc.employee, ['employee_number', 'company'], function(r) {
				if (r) {
					if (r.employee_number) {
						frm.set_value('employee_id', r.employee_number);
					}
					if (r.company) {
						frm.set_value('company', r.company);
					}
				}
			});
			
			// Show last warning if any
			frappe.call({
				method: 'chundakadan.chundakadan.doctype.warning_letter.warning_letter.get_employee_last_warning',
				args: {
					employee: frm.doc.employee
				},
				callback: function(r) {
					if (r.message) {
						frappe.msgprint({
							title: __('Previous Warning'),
							message: `Last warning issued on ${r.message.warning_date}: <b>${r.message.warning_type}</b> for ${r.message.violation_type}`,
							indicator: 'orange'
						});
					}
				}
			});
		}
	},
	
	company: function(frm) {
		if (frm.doc.company) {
			// Fetch company address
			frappe.db.get_value('Company', frm.doc.company, 'company_address', function(r) {
				if (r && r.company_address) {
					frappe.db.get_value('Address', r.company_address, 'address_line1', function(addr) {
						if (addr) {
							frm.set_value('company_address', addr.address_line1);
						}
					});
				}
			});
		}
	},
	
	warning_type: function(frm) {
		update_subject_and_content(frm);
		update_next_consequence(frm);
	},
	
	violation_type: function(frm) {
		update_subject_and_content(frm);
		
		// Set default penalty based on violation type
		if (!frm.doc.penalty_type) {
			if (frm.doc.violation_type === 'Negligence of Duty') {
				frm.set_value('penalty_type', 'Salary Deduction');
				frm.set_value('salary_deduction_days', 1);
			}
		}
	},
	
	penalty_type: function(frm) {
		if (frm.doc.penalty_type !== 'Salary Deduction') {
			frm.set_value('salary_deduction_days', 0);
			frm.set_value('penalty_amount', 0);
		}
	},
	
	salary_deduction_days: function(frm) {
		calculate_penalty(frm);
	},
	
	warning_date: function(frm) {
		if (!frm.doc.gm_signature_date) {
			frm.set_value('gm_signature_date', frm.doc.warning_date);
		}
	}
});

function update_subject_and_content(frm) {
	if (frm.doc.warning_type && frm.doc.violation_type) {
		if (!frm.doc.subject || confirm('Update subject to default?')) {
			frm.set_value('subject', get_default_subject(frm.doc.warning_type, frm.doc.violation_type));
		}
		
		// Trigger auto-generation of letter content
		frm.trigger('generate_letter_content');
	}
}

function get_default_subject(warning_type, violation_type) {
	return `${warning_type} for ${violation_type}`;
}

function update_next_consequence(frm) {
	let consequences = {
		'First Warning': 'Any further violations will result in a Second Warning with increased penalties.',
		'Second Warning': 'Any further violations will result in a Final Warning and may lead to suspension.',
		'Final Warning': 'Any further violations will result in termination of employment.',
		'Show Cause Notice': 'Failure to provide satisfactory explanation may result in immediate termination.'
	};
	
	if (frm.doc.warning_type && !frm.doc.next_consequence) {
		frm.set_value('next_consequence', consequences[frm.doc.warning_type]);
	}
}

function calculate_penalty(frm) {
	if (frm.doc.penalty_type === 'Salary Deduction' && frm.doc.salary_deduction_days && frm.doc.employee) {
		// This will be calculated on the server side
		frm.trigger('validate');
	}
}

function show_warning_history(frm) {
	if (frm.doc.employee) {
		frappe.call({
			method: 'chundakadan.chundakadan.doctype.warning_letter.warning_letter.get_employee_warning_count',
			args: {
				employee: frm.doc.employee
			},
			callback: function(r) {
				if (r.message && r.message > 0) {
					let warning_level = '';
					let color = 'orange';
					
					if (r.message === 1) {
						warning_level = 'This will be the Second Warning';
						color = 'orange';
					} else if (r.message === 2) {
						warning_level = 'This will be the Final Warning';
						color = 'red';
					} else if (r.message >= 3) {
						warning_level = 'Employee has already received multiple warnings. Consider termination.';
						color = 'red';
					}
					
					if (warning_level) {
						frm.dashboard.add_indicator(__(warning_level), color);
					}
				}
			}
		});
	}
}

frappe.ui.form.on('Warning Letter', {
	generate_letter_content: function(frm) {
		// Auto-generate letter content
		if (frm.doc.employee_name && frm.doc.violation_type && frm.doc.warning_type) {
			// Content will be generated on server side during validation
			frm.save();
		}
	}
});
