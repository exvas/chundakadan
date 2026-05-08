//code written by niranjana nir
frappe.ui.form.on('Leave Application', {
    refresh: function (frm) {
        // Add approval buttons in Actions menu based on current user and approval status
        if (!frm.is_new() && frm.doc.docstatus === 0) {
            add_approval_buttons(frm);
        }

        // Show approval status indicator (contextual based on current user)
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
            employee_name: frm.doc.employee_name,
            employee: frm.doc.employee
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
    const custom_approval_status = frm.doc.custom_approval_status;
    const hrms_status = frm.doc.status;

    // Don't show buttons if already fully approved or no status set
    if (!custom_approval_status || hrms_status === "Approved") {
        return;
    }

    // Only relevant for Pending or intermediate Approved statuses
    if (!custom_approval_status.startsWith("Pending") &&
        !(custom_approval_status.startsWith("Approved") && hrms_status !== "Approved")) {
        return;
    }

    // Always use backend check to verify eligibility (handles all email/designation scenarios)
    // This is the most reliable approach for both local and production environments
    frappe.call({
        method: 'chundakadan.doc_events.leave_application.check_user_can_approve',
        args: {
            doc_name: frm.doc.name,
            user: current_user
        },
        callback: function (r) {
            if (r.message && r.message.can_approve) {
                _render_approval_buttons(frm);
            } else {
                // Explicitly clear actions if user is not authorized
                // This prevents previous approvers from seeing cached or default buttons
                frm.page.clear_actions_menu();
            }
        }
    });
}

function _render_approval_buttons(frm) {
    // Clear existing action items first
    frm.page.clear_actions_menu();

    // Add Approve option
    frm.page.add_action_item(__('Approve'), function () {
        approve_leave_application(frm, 'approve');
    });

    // Add Reject option
    frm.page.add_action_item(__('Reject'), function () {
        frappe.confirm(
            __('Are you sure you want to reject this leave application?'),
            function () {
                approve_leave_application(frm, 'reject');
            }
        );
    });
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
    const hrms_status = frm.doc.status;

    if (!status) return;

    let indicator_color = 'blue';

    // Determine indicator color based on status
    // Everyone sees the actual stored status value
    if (hrms_status === "Approved") {
        indicator_color = 'green';
    } else if (status.startsWith("Approved")) {
        indicator_color = 'blue';
    } else if (status === 'Rejected') {
        indicator_color = 'red';
    } else if (status.startsWith('Pending')) {
        indicator_color = 'orange';
    }

    // Update the page indicator with actual status
    frm.page.set_indicator(status, indicator_color);
}
