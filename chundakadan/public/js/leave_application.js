//code written by niranjana
frappe.ui.form.on('Leave Application', {
    refresh: function (frm) {
        // Add approval buttons in Actions menu based on current user and approval status
        if (!frm.is_new() && frm.doc.docstatus === 0) {
            add_approval_buttons(frm);
        }

        // Show approval status indicator
        show_approval_status_indicator(frm);
    },

    onload: function (frm) {
        // Set initial approval status for new documents
        if (frm.is_new() && !frm.doc.custom_approval_status) {
            frm.set_value('custom_approval_status', 'Pending');
        }
    },

    employee: function (frm) {
        // When employee is selected, fetch and set the approver details
        if (frm.doc.employee && frm.doc.employee_name) {
            set_approver_for_employee(frm);
        }
    },

    employee_name: function (frm) {
        // Also trigger when employee_name changes (fetched from employee)
        if (frm.doc.employee_name) {
            set_approver_for_employee(frm);
        }
    }
});

function set_approver_for_employee(frm) {
    frappe.call({
        method: 'chundakadan.doc_events.leave_application.get_approver_for_employee',
        args: {
            employee_name: frm.doc.employee_name
        },
        callback: function (r) {
            if (r.message) {
                frm.set_value('leave_approver', r.message.leave_approver);
                frm.set_value('leave_approver_name', r.message.leave_approver_name);
                frm.set_value('custom_approval_status', r.message.custom_approval_status);
            }
        }
    });
}

function add_approval_buttons(frm) {
    const current_user = frappe.session.user;
    const leave_approver = frm.doc.leave_approver;
    const custom_approval_status = frm.doc.custom_approval_status;

    // Only show Approve/Reject for the designated approver when status is pending
    if (custom_approval_status && custom_approval_status.startsWith("Pending")) {
        // Check if current user is the designated approver
        if (current_user === leave_approver) {
            // Clear all existing items in the Actions menu and add our options
            setTimeout(function () {
                // Remove all items from Actions menu
                frm.page.clear_actions_menu();

                // Add only Approve option
                frm.page.add_action_item(__('Approve'), function () {
                    approve_leave_application(frm, 'approve');
                });

                // Add only Reject option
                frm.page.add_action_item(__('Reject'), function () {
                    frappe.confirm(
                        __('Are you sure you want to reject this leave application?'),
                        function () {
                            approve_leave_application(frm, 'reject');
                        }
                    );
                });
            }, 100);
        } else {
            // For non-approvers (employees), clear the Actions menu completely
            setTimeout(function () {
                frm.page.clear_actions_menu();
            }, 100);
        }
    }
}

function approve_leave_application(frm, action) {
    frappe.call({
        method: 'chundakadan.doc_events.leave_application.approve_leave',
        args: {
            doc_name: frm.doc.name,
            approval_action: action
        },
        freeze: true,
        freeze_message: action === 'approve' ? __('Approving...') : __('Rejecting...'),
        callback: function (r) {
            if (r.message && r.message.success) {
                frm.reload_doc();
            }
        }
    });
}

function show_approval_status_indicator(frm) {
    const status = frm.doc.custom_approval_status;

    if (!status) return;

    let indicator_color = 'blue';

    if (status === 'Approved') {
        indicator_color = 'green';
    } else if (status === 'Rejected') {
        indicator_color = 'red';
    } else if (status.startsWith('Pending')) {
        indicator_color = 'orange';
    } else if (status.startsWith('Approved')) {
        indicator_color = 'blue';
    }

    // Update the page indicator
    frm.page.set_indicator(status, indicator_color);
}
