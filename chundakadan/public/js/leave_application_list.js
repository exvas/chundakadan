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
    "Approved GM": { approver: APPROVERS.GM, next_status: "Pending GM" }
};

// Store original formatters
const original_formatters = frappe.listview_settings['Leave Application'].formatters || {};

frappe.listview_settings['Leave Application'].formatters = Object.assign({}, original_formatters, {
    custom_approval_status: function (value, df, doc) {
        if (!value) return '';

        const current_user = frappe.session.user;
        const hrms_status = doc.status;  // HRMS standard status field
        let display_status = value;
        let indicator_color = 'blue';

        // If HRMS status is "Approved", this is final approval - show green
        if (hrms_status === "Approved") {
            display_status = value;  // Keep showing "Approved GM" or "Approved HR"
            indicator_color = 'green';
        }
        // For intermediate "Approved X" statuses (HRMS not yet Approved), show contextual status
        else if (value.startsWith("Approved")) {
            const info = STATUS_INFO[value];
            if (info) {
                if (current_user === info.approver) {
                    // Current user is the one who approved - show "Approved X"
                    display_status = value;
                    indicator_color = 'blue';
                } else {
                    // All other users see the next pending status
                    display_status = info.next_status;
                    indicator_color = 'orange';
                }
            }
        } else if (value === 'Rejected') {
            indicator_color = 'red';
        } else if (value.startsWith('Pending')) {
            indicator_color = 'orange';
        }

        return `<span class="indicator-pill ${indicator_color}">${display_status}</span>`;
    }
});
