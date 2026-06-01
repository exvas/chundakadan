// Copyright (c) 2026, Ashkar and contributors
// For license information, please see license.txt

frappe.ui.form.on('Leave Application', {
    refresh: function (frm) {
        // Enforce the approval_flow child table to be read-only in the UI
        frm.set_df_property('approval_flow', 'read_only', 1);

        // Hide the standard "Submit" button when the doc is Draft.
        // Submission is owned by chundakadan's approval chain — the final
        // approver clicking Approve in approve_leave() is what calls
        // doc.submit(). Letting the user click Submit here would bypass
        // the chain entirely and put balance on an unapproved leave.
        //
        // setTimeout because Frappe wires the primary action AFTER our
        // refresh handler runs.
        if (frm.doc.docstatus === 0 && !frm.is_new()) {
            setTimeout(function () {
                if (frm.page && frm.page.btn_primary) {
                    frm.page.btn_primary.hide();
                }
                // Fallback selector in case Frappe re-renders the bar
                $(frm.page.wrapper).find('.primary-action').filter(function () {
                    return $(this).text().trim().toLowerCase() === 'submit';
                }).hide();
            }, 50);
        }

        // Show Approve / Reject buttons when:
        //  - the doc is Draft (0) or Submitted (1) — chundakadan's chain
        //    advances on Submitted docs, not just Drafts
        //  - the chain isn't already finalized
        //  - the caller is authorized (mirrors leave.py:_caller_can_act_on):
        //      * Administrator
        //      * current_approver (the resolved user for this step)
        //      * leave_approver (the standard ERPNext field)
        //      * holds the role of the current step
        //    Last condition unblocks any HR/GM Leave Approver who wants to act
        //    on a leave the chain happened to resolve to a different user.
        const is_open = frm.doc.docstatus !== 2 &&
            !['Approved', 'Rejected'].includes(frm.doc.custom_approval_status || '');

        let current_step_role = null;
        if (Array.isArray(frm.doc.approval_flow) && frm.doc.approval_flow.length) {
            const idx = frm.doc.current_approval_index || 0;
            if (idx >= 0 && idx < frm.doc.approval_flow.length) {
                current_step_role = frm.doc.approval_flow[idx].approver_role;
            }
        }
        const user_roles = frappe.user_roles || [];
        const is_authorized =
            frappe.session.user === 'Administrator' ||
            frm.doc.current_approver === frappe.session.user ||
            (frm.doc.leave_approver && frm.doc.leave_approver === frappe.session.user) ||
            (current_step_role && user_roles.includes(current_step_role));

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

