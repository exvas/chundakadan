// Copyright (c) 2026, Ashkar and contributors
// For license information, please see license.txt

frappe.ui.form.on('Leave Application', {
    refresh: function (frm) {
        // Enforce the approval_flow child table to be read-only in the UI
        frm.set_df_property('approval_flow', 'read_only', 1);

        // Show Approve / Reject buttons when:
        //  - the doc is Draft (0) or Submitted (1) — chundakadan's chain
        //    advances on Submitted docs, not just Drafts
        //  - the chain isn't already finalized
        //  - the caller is the current approver (or Administrator)
        const is_open = frm.doc.docstatus !== 2 &&
            !['Approved', 'Rejected'].includes(frm.doc.custom_approval_status || '');
        const is_authorized = frm.doc.current_approver === frappe.session.user ||
            frappe.session.user === 'Administrator';
        if (is_open && is_authorized && frm.doc.current_approver) {
            frm.add_custom_button(__('Approve'), function () {
                approve_leave_application(frm);
            }, __('Actions')).addClass('btn-primary');

            frm.add_custom_button(__('Reject'), function () {
                reject_leave_application(frm);
            }, __('Actions')).addClass('btn-danger');

            // Style the Actions dropdown trigger black. Inline .css() is
            // safe — it only affects the current form's button; other
            // doctypes' Actions menus stay default. setTimeout waits for
            // Frappe to finish rendering the button group.
            setTimeout(function () {
                $('.inner-group-button[data-label="Actions"] > button.btn').css({
                    'background-color': '#000',
                    'color': '#fff',
                    'border-color': '#000',
                });
            }, 100);
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

