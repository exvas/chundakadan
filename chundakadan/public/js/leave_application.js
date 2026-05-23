// Copyright (c) 2026, Ashkar and contributors
// For license information, please see license.txt

frappe.ui.form.on('Leave Application', {
    refresh: function (frm) {
        // Enforce the approval_flow child table to be read-only in the UI
        frm.set_df_property('approval_flow', 'read_only', 1);

        // Show Approve and Reject buttons if the document is a draft (not submitted/cancelled)
        // and the current logged-in user is the designated current approver
        if (frm.doc.docstatus === 0 && frm.doc.current_approver === frappe.session.user) {
            frm.add_custom_button(__('Approve'), function () {
                approve_leave_application(frm);
            }, __('Actions')).addClass('btn-primary');

            frm.add_custom_button(__('Reject'), function () {
                reject_leave_application(frm);
            }, __('Actions')).addClass('btn-danger');
        }

        // Apply premium custom indicator to reflect the approval workflow status
        update_approval_indicator(frm);
    }
});

/**
 * Calls backend approve_leave method, reloads document on success.
 */
function approve_leave_application(frm) {
    frappe.confirm(
        __('Are you sure you want to approve this leave application?'),
        function () {
            frappe.call({
                method: 'chundakadan.chundakadan.api.leave.approve_leave',
                args: {
                    docname: frm.doc.name
                },
                freeze: true,
                freeze_message: __('Processing approval...'),
                callback: function (r) {
                    if (r.message && r.message.success) {
                        frm.reload_doc();
                    }
                }
            });
        }
    );
}

/**
 * Prompts the user for a rejection reason, calls backend reject_leave method, and reloads.
 */
function reject_leave_application(frm) {
    frappe.prompt(
        [
            {
                label: __('Remarks / Reason for Rejection'),
                fieldname: 'remarks',
                fieldtype: 'Small Text',
                reqd: true
            }
        ],
        function (values) {
            frappe.call({
                method: 'chundakadan.chundakadan.api.leave.reject_leave',
                args: {
                    docname: frm.doc.name,
                    remarks: values.remarks
                },
                freeze: true,
                freeze_message: __('Processing rejection...'),
                callback: function (r) {
                    if (r.message && r.message.success) {
                        frm.reload_doc();
                    }
                }
            });
        },
        __('Reject Leave Application'),
        __('Submit')
    );
}

/**
 * Updates form indicator bar color and text dynamically.
 */
function update_approval_indicator(frm) {
    if (frm.doc.custom_approval_status) {
        let color = 'orange'; // default for Pending
        
        if (frm.doc.custom_approval_status === 'Approved') {
            color = 'green';
        } else if (frm.doc.custom_approval_status === 'Rejected') {
            color = 'red';
        } else if (frm.doc.custom_approval_status === 'Partially Approved') {
            color = 'blue';
        }
        
        frm.page.set_indicator(__(frm.doc.custom_approval_status), color);
    }
}

