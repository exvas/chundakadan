// Copyright (c) 2025, TBO Cloud and contributors
// For license information, please see license.txt

frappe.ui.form.on('Disciplinary Investigation Incident Report', {
	refresh: function(frm) {
		// Set default report date if empty
		if (!frm.doc.report_date) {
			frm.set_value('report_date', frappe.datetime.get_today());
		}
		
		// Add custom buttons based on status
		if (frm.doc.docstatus === 1) {
			// Complete Investigation button
			if (frm.doc.status !== 'Action Taken') {
				frm.add_custom_button(__('Complete Investigation'), function() {
					frappe.call({
						method: 'complete_investigation',
						doc: frm.doc,
						callback: function(r) {
							frm.reload_doc();
						}
					});
				}).addClass('btn-primary');
			}
			
			// Show incident statistics
			frappe.call({
				method: 'chundakadan.chundakadan.doctype.disciplinary_investigation_incident_report.disciplinary_investigation_incident_report.get_incident_statistics',
				callback: function(r) {
					if (r.message) {
						frm.dashboard.add_indicator(__('Total Incidents: {0}', [r.message.total_incidents]), 'blue');
						if (r.message.investigating > 0) {
							frm.dashboard.add_indicator(__('Investigating: {0}', [r.message.investigating]), 'orange');
						}
					}
				}
			});
		}
		
		// Color code based on status
		if (frm.doc.status) {
			let color_map = {
				'Draft': 'gray',
				'Investigating': 'orange',
				'Completed': 'blue',
				'Action Taken': 'green',
				'Cancelled': 'red'
			};
			frm.set_df_property('status', 'color', color_map[frm.doc.status] || 'gray');
		}
		
		// Highlight critical actions
		if (frm.doc.termination || frm.doc.suspension) {
			frm.dashboard.add_indicator(__('Critical Action Required'), 'red');
		}
	},
	
	supervisor_manager: function(frm) {
		// Fetch supervisor details
		if (frm.doc.supervisor_manager) {
			frappe.db.get_value('Employee', frm.doc.supervisor_manager, 
				['employee_number', 'cell_number', 'designation'], 
				function(r) {
					if (r) {
						frm.set_value('supervisor_staff_id', r.employee_number);
						frm.set_value('supervisor_contact_no', r.cell_number);
						frm.set_value('supervisor_designation', r.designation);
					}
				}
			);
		}
	},
	
	date_of_incident: function(frm) {
		validate_incident_date(frm);
	},
	
	prepared_by: function(frm) {
		if (frm.doc.prepared_by && !frm.doc.prepared_by_date) {
			frm.set_value('prepared_by_date', frappe.datetime.get_today());
		}
	},
	
	verified_by: function(frm) {
		if (frm.doc.verified_by && !frm.doc.verified_by_date) {
			frm.set_value('verified_by_date', frappe.datetime.get_today());
		}
	},
	
	written_warning: function(frm) {
		if (frm.doc.written_warning) {
			frappe.msgprint({
				title: __('Written Warning'),
				message: __('A warning letter will be created upon submission of this report'),
				indicator: 'orange'
			});
		}
	},
	
	termination: function(frm) {
		if (frm.doc.termination) {
			frappe.msgprint({
				title: __('Termination'),
				message: __('Please ensure all termination procedures are followed'),
				indicator: 'red'
			});
		}
	}
});

// Employee Involved table events
frappe.ui.form.on('Incident Employee', {
	employee_name: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.employee_name) {
			// Show employee incident history
			frappe.call({
				method: 'chundakadan.chundakadan.doctype.disciplinary_investigation_incident_report.disciplinary_investigation_incident_report.get_employee_incident_history',
				args: {
					employee: row.employee_name
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						frappe.msgprint({
							title: __('Employee Incident History'),
							message: __('This employee has been involved in {0} previous incident(s)', [r.message.length]),
							indicator: 'orange'
						});
					}
				}
			});
		}
	}
});

function validate_incident_date(frm) {
	if (frm.doc.date_of_incident) {
		let incident_date = frappe.datetime.str_to_obj(frm.doc.date_of_incident);
		let today = frappe.datetime.str_to_obj(frappe.datetime.get_today());
		
		if (incident_date > today) {
			frappe.msgprint({
				title: __('Invalid Date'),
				message: __('Incident date cannot be in the future'),
				indicator: 'red'
			});
			frm.set_value('date_of_incident', '');
		}
	}
}

// Auto-set signature dates
frappe.ui.form.on('Disciplinary Investigation Incident Report', {
	before_save: function(frm) {
		// Set signature dates if signatures are present but dates are missing
		if (frm.doc.prepared_by_signature && !frm.doc.prepared_by_date) {
			frm.set_value('prepared_by_date', frappe.datetime.get_today());
		}
		
		if (frm.doc.verified_by_signature && !frm.doc.verified_by_date) {
			frm.set_value('verified_by_date', frappe.datetime.get_today());
		}
		
		if (frm.doc.employee_signature && !frm.doc.employee_signature_date) {
			frm.set_value('employee_signature_date', frappe.datetime.get_today());
		}
	}
});
