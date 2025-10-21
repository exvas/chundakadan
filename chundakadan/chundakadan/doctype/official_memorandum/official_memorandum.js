// Copyright (c) 2025, TBO Cloud and contributors
// For license information, please see license.txt

frappe.ui.form.on('Official Memorandum', {
	refresh: function(frm) {
		// Add custom buttons based on status
		if (frm.doc.docstatus === 1) {
			// Acknowledge button for employees
			if (frm.doc.status === 'Issued' && frm.doc.acknowledgment_required) {
				frm.add_custom_button(__('Acknowledge'), function() {
					frappe.call({
						method: 'acknowledge_memo',
						doc: frm.doc,
						callback: function(r) {
							frm.reload_doc();
						}
					});
				}).addClass('btn-primary');
			}
			
			// Send Email button
			frm.add_custom_button(__('Send Email to All Staff'), function() {
				send_memo_email(frm);
			}, __('Actions'));
			
			// Show statistics
			frappe.call({
				method: 'chundakadan.chundakadan.doctype.official_memorandum.official_memorandum.get_memo_statistics',
				callback: function(r) {
					if (r.message) {
						frm.dashboard.add_indicator(__('Total Memos: {0}', [r.message.total_memos]), 'blue');
						frm.dashboard.add_indicator(__('This Month: {0}', [r.message.this_month]), 'green');
					}
				}
			});
		}
		
		// Load Template button
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Load Template'), function() {
				load_template_dialog(frm);
			});
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
		
		// Show acknowledgment count
		if (frm.doc.acknowledged_by) {
			let count = frm.doc.acknowledged_by.split('\n').length;
			frm.dashboard.add_indicator(__('Acknowledged by {0} employee(s)', [count]), 'green');
		}
	},
	
	subject: function(frm) {
		// Auto-suggest content based on subject keywords
		if (frm.doc.subject && !frm.doc.memo_content) {
			if (frm.doc.subject.toLowerCase().includes('communication')) {
				frappe.msgprint({
					title: __('Template Available'),
					message: __('Click "Load Template" to use the Communication Policy template'),
					indicator: 'blue'
				});
			}
		}
	},
	
	memo_date: function(frm) {
		if (!frm.doc.gm_signature_date) {
			frm.set_value('gm_signature_date', frm.doc.memo_date);
		}
	}
});

function load_template_dialog(frm) {
	frappe.call({
		method: 'chundakadan.chundakadan.doctype.official_memorandum.official_memorandum.get_memo_templates',
		callback: function(r) {
			if (r.message) {
				let templates = r.message;
				let template_options = Object.keys(templates);
				
				frappe.prompt(
					{
						label: 'Select Template',
						fieldname: 'template',
						fieldtype: 'Select',
						options: template_options,
						reqd: 1
					},
					function(values) {
						let selected_template = templates[values.template];
						
						// Set values from template
						frm.set_value('subject', selected_template.subject);
						frm.set_value('recipients_to', selected_template.recipients_to);
						frm.set_value('greeting', selected_template.greeting);
						frm.set_value('memo_content', selected_template.memo_content);
						frm.set_value('instructions', selected_template.instructions);
						frm.set_value('consequences', selected_template.consequences);
						frm.set_value('closing_message', selected_template.closing_message);
						frm.set_value('clarification_contact', selected_template.clarification_contact);
						
						frappe.show_alert({
							message: __('Template loaded successfully'),
							indicator: 'green'
						});
					},
					__('Load Memo Template')
				);
			}
		}
	});
}

function send_memo_email(frm) {
	frappe.prompt(
		{
			label: 'Email Content',
			fieldname: 'email_content',
			fieldtype: 'Text',
			default: `${frm.doc.greeting}\n\n${frappe.utils.html2text(frm.doc.memo_content)}\n\n${frm.doc.thank_you_message}`
		},
		function(values) {
			frappe.call({
				method: 'frappe.core.doctype.communication.email.make',
				args: {
					recipients: 'all',
					subject: `OFFICIAL MEMORANDUM: ${frm.doc.subject}`,
					content: values.email_content,
					doctype: frm.doc.doctype,
					name: frm.doc.name,
					send_email: 1
				},
				callback: function() {
					frappe.msgprint(__('Email sent successfully to all staff'));
				}
			});
		},
		__('Send Memorandum Email')
	);
}

// Auto-format memo header
frappe.ui.form.on('Official Memorandum', {
	onload: function(frm) {
		// Set default greeting if empty
		if (!frm.doc.greeting) {
			frm.set_value('greeting', 'Dear Team,');
		}
		
		// Set default thank you message
		if (!frm.doc.thank_you_message) {
			frm.set_value('thank_you_message', 'Thank you for your cooperation.');
		}
	},
	
	before_save: function(frm) {
		// Auto-set signature date if signature is present
		if (frm.doc.gm_signature && !frm.doc.gm_signature_date) {
			frm.set_value('gm_signature_date', frappe.datetime.get_today());
		}
	}
});
