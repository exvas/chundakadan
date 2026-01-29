//code written by niranjana
// List view customization for Leave Application - shows contextual approval status

frappe.listview_settings['Leave Application'] = frappe.listview_settings['Leave Application'] || {};

// Approver emails - should match the Python APPROVERS dict
const APPROVERS = {
    "HOD": "chundakadannorthasm@gmail.com",
    "HR": "binduudayan334@gmail.com",
    "GM": "chundakadangm@gmail.com"
};

// Status mapping for contextual display
const STATUS_INFO = {
    "Approved HOD": { approver: APPROVERS.HOD, next_status: "Pending HR" },
    "Approved HR": { approver: APPROVERS.HR, next_status: "Pending GM" },
    "Approved GM": { approver: APPROVERS.GM, next_status: "Approved" }
};

// Store original formatters
const original_formatters = frappe.listview_settings['Leave Application'].formatters || {};

frappe.listview_settings['Leave Application'].formatters = Object.assign({}, original_formatters, {
    custom_approval_status: function (value, df, doc) {
        if (!value) return '';

        const current_user = frappe.session.user;
        let display_status = value;
        let indicator_color = 'blue';

        // For intermediate "Approved X" statuses, show contextual status
        if (value.startsWith("Approved") && value !== "Approved") {
            const info = STATUS_INFO[value];
            if (info) {
                if (current_user === info.approver) {
                    // Current user is the one who approved - show "Approved X"
                    display_status = value;
                    indicator_color = 'blue';
                } else {
                    // All other users see the next pending status
                    display_status = info.next_status;
                    if (info.next_status === "Approved") {
                        indicator_color = 'green';
                    } else {
                        indicator_color = 'orange';
                    }
                }
            }
        } else if (value === 'Approved') {
            indicator_color = 'green';
        } else if (value === 'Rejected') {
            indicator_color = 'red';
        } else if (value.startsWith('Pending')) {
            indicator_color = 'orange';
        }

        return `<span class="indicator-pill ${indicator_color}">${display_status}</span>`;
    }
});
