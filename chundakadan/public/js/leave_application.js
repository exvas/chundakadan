//code written by niranjana
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

    // Check if buttons should be shown:
    // 1. For "Pending X" status - show to the designated approver
    // 2. For "Approved X" status (intermediate) - show to the next approver (leave_approver field)

    let should_show_buttons = false;

    if (custom_approval_status) {
        if (custom_approval_status.startsWith("Pending") && current_user === leave_approver) {
            // Pending status - current user is the designated approver
            should_show_buttons = true;
        } else if (custom_approval_status.startsWith("Approved") &&
            custom_approval_status !== "Approved" &&
            current_user === leave_approver) {
            // Intermediate "Approved X" status - current user is the next approver
            should_show_buttons = true;
        }
    }

    // Function to setup action buttons
    function setup_action_buttons() {
        // Remove all items from Actions menu
        frm.page.clear_actions_menu();

        if (should_show_buttons) {
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
    }

    // Only proceed if there's a status to handle
    if (custom_approval_status &&
        (custom_approval_status.startsWith("Pending") ||
            (custom_approval_status.startsWith("Approved") && custom_approval_status !== "Approved"))) {

        // Setup buttons with multiple delays to ensure they appear
        // First attempt - immediate after short delay
        setTimeout(setup_action_buttons, 300);

        // Second attempt - backup after page is more likely to be fully loaded
        setTimeout(setup_action_buttons, 800);
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
    const current_user = frappe.session.user;
    const leave_approver = frm.doc.leave_approver;

    if (!status) return;

    // Approver emails - should match the Python APPROVERS dict
    const APPROVERS = {
        "HOD": "chundakadannorthasm@gmail.com",
        "HR": "binduudayan334@gmail.com",
        "GM": "chundakadangm@gmail.com"
    };

    let display_status = status;
    let indicator_color = 'blue';

    // For intermediate "Approved X" statuses, show contextual status
    // Only the specific approver who approved sees "Approved X"
    // Everyone else sees the next pending status
    if (status.startsWith("Approved") && status !== "Approved") {
        // Mapping: status -> {approver_email, next_pending_status}
        const status_info = {
            "Approved HOD": { approver: APPROVERS.HOD, next_status: "Pending HR" },
            "Approved HR": { approver: APPROVERS.HR, next_status: "Pending GM" },
            "Approved GM": { approver: APPROVERS.GM, next_status: "Approved" }
        };

        const info = status_info[status];
        if (info) {
            if (current_user === info.approver) {
                // Current user is the one who approved - show "Approved X"
                display_status = status;
                indicator_color = 'blue';
            } else {
                // All other users see the next pending status
                display_status = info.next_status;
                if (info.next_status === "Approved") {
                    indicator_color = 'green';
                } else {
                    indicator_color = 'orange';  // Pending color
                }
            }
        }
    } else if (status === 'Approved') {
        indicator_color = 'green';
    } else if (status === 'Rejected') {
        indicator_color = 'red';
    } else if (status.startsWith('Pending')) {
        indicator_color = 'orange';
    }

    // Update the page indicator with contextual status
    frm.page.set_indicator(display_status, indicator_color);

    // Update the field display value without marking form as dirty
    if (display_status !== status) {
        // Directly update the displayed value without triggering change events
        // This updates the display only, not the actual saved value
        frm.doc.custom_approval_status = display_status;
        frm.refresh_field('custom_approval_status');
    }
}
