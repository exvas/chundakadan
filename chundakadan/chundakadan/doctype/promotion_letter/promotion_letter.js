// Copyright (c) 2025, TBO Cloud and contributors
// For license information, please see license.txt

frappe.ui.form.on('Promotion Letter', {
	refresh: function(frm) {
		// Set default subject if empty
		if (!frm.doc.subject && frm.doc.new_position) {
			frm.set_value('subject', `Promotion to ${frm.doc.new_position}`);
		}
		
		// Add custom buttons based on status
		if (frm.doc.docstatus === 1) {
			// Show promotion history
			if (frm.doc.employee) {
				show_promotion_history(frm);
			}
			
			// Add accept/reject buttons for employees
			if (frm.doc.status === 'Issued' && frm.doc.employee_acceptance && !frm.doc.employee_signature_date) {
				frm.add_custom_button(__('Accept Promotion'), function() {
					frappe.confirm(
						'Are you sure you want to accept this promotion?',
						function() {
							frappe.call({
								method: 'accept_promotion',
								doc: frm.doc,
								callback: function(r) {
									frappe.msgprint({
										title: __('Congratulations!'),
										message: __('Promotion accepted successfully. Your employee record has been updated.'),
										indicator: 'green'
									});
									frm.reload_doc();
								}
							});
						}
					);
				}).addClass('btn-primary');
				
				frm.add_custom_button(__('Reject Promotion'), function() {
					frappe.prompt(
						{
							label: 'Reason for Rejection',
							fieldname: 'reason',
							fieldtype: 'Small Text',
							reqd: 1
						},
						function(values) {
							frappe.call({
								method: 'reject_promotion',
								doc: frm.doc,
								args: {
									reason: values.reason
								},
								callback: function(r) {
									frm.reload_doc();
								}
							});
						},
						__('Reject Promotion')
					);
				}, __('Actions'));
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
				'Issued': 'blue',
				'Accepted': 'green',
				'Rejected': 'red',
				'Cancelled': 'red'
			};
			frm.set_df_property('status', 'color', color_map[frm.doc.status] || 'gray');
		}
		
		// Highlight salary increment
		if (frm.doc.salary_increment && frm.doc.salary_increment > 0) {
			frm.dashboard.add_indicator(__('Salary Increment: ₹{0}', [format_currency(frm.doc.salary_increment)]), 'green');
		}
	},
	
	employee: function(frm) {
		if (frm.doc.employee) {
			// Fetch employee details
			frappe.db.get_value('Employee', frm.doc.employee, 
				['employee_number', 'designation', 'department', 'grade', 'company', 'ctc', 'reports_to'], 
				function(r) {
					if (r) {
						if (r.employee_number) {
							frm.set_value('employee_id', r.employee_number);
						}
						if (r.designation) {
							frm.set_value('current_position', r.designation);
						}
						if (r.department) {
							frm.set_value('current_department', r.department);
						}
						if (r.grade) {
							frm.set_value('current_grade', r.grade);
						}
						if (r.company) {
							frm.set_value('company', r.company);
						}
					}
				}
			);
			
			// Show promotion history
			if (frm.doc.docstatus === 0) {
				show_promotion_history(frm);
			}
		}
	},
	
	new_position: function(frm) {
		if (frm.doc.new_position) {
			// Update subject
			frm.set_value('subject', `Promotion to ${frm.doc.new_position}`);
		}
	},
	
	new_salary: function(frm) {
		calculate_increment(frm);
	},
	
	effective_date: function(frm) {
		if (frm.doc.effective_date && !frm.doc.gm_signature_date) {
			frm.set_value('gm_signature_date', frm.doc.effective_date);
		}
	},
	
	promotion_date: function(frm) {
		if (!frm.doc.gm_signature_date) {
			frm.set_value('gm_signature_date', frm.doc.promotion_date);
		}
		
		// Set effective date to 1 month from promotion date if not set
		if (!frm.doc.effective_date) {
			let effective = frappe.datetime.add_days(frm.doc.promotion_date, 30);
			frm.set_value('effective_date', effective);
		}
	}
});

function calculate_increment(frm) {
	if (frm.doc.new_salary && frm.doc.employee) {
		frappe.db.get_value('Employee', frm.doc.employee, 'ctc', function(r) {
			if (r && r.ctc) {
				let increment = frm.doc.new_salary - r.ctc;
				frm.set_value('salary_increment', increment);
				
				if (increment > 0) {
					let percentage = ((increment / r.ctc) * 100).toFixed(2);
					frappe.show_alert({
						message: __('Salary increase: {0}%', [percentage]),
						indicator: 'green'
					});
				}
			}
		});
	}
}

function show_promotion_history(frm) {
	if (frm.doc.employee) {
		frappe.call({
			method: 'chundakadan.chundakadan.doctype.promotion_letter.promotion_letter.get_employee_promotion_history',
			args: {
				employee: frm.doc.employee
			},
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					let history_html = '<table class="table table-bordered"><thead><tr><th>Date</th><th>From</th><th>To</th><th>Status</th></tr></thead><tbody>';
					r.message.forEach(function(promo) {
						history_html += `<tr>
							<td>${promo.promotion_date}</td>
							<td>${promo.current_position || 'N/A'}</td>
							<td>${promo.new_position}</td>
							<td><span class="indicator ${promo.status === 'Accepted' ? 'green' : 'blue'}">${promo.status}</span></td>
						</tr>`;
					});
					history_html += '</tbody></table>';
					
					frm.dashboard.add_section(
						`<div class="form-dashboard-section custom">
							<h5>Promotion History (${r.message.length})</h5>
							${history_html}
						</div>`
					);
				}
			}
		});
	}
}

// Auto-generate content when key fields change
frappe.ui.form.on('Promotion Letter', {
	before_save: function(frm) {
		// Ensure employee acceptance text is set
		if (frm.doc.employee_acceptance && !frm.doc.employee_acceptance_text && frm.doc.employee_name && frm.doc.new_position) {
			frm.set_value('employee_acceptance_text', 
				`I, ${frm.doc.employee_name}, accept the promotion to the position of ${frm.doc.new_position} as outlined above.`
			);
		}
	}
});
