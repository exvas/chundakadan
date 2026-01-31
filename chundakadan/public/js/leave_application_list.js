//code written by niranjana nir
// List view customization for Leave Application - shows contextual approval status

frappe.listview_settings['Leave Application'] = frappe.listview_settings['Leave Application'] || {};

// GM email - should match the Python APPROVERS dict
const GM_EMAIL = "chundakadangm@gmail.com";

// Store original formatters
const original_formatters = frappe.listview_settings['Leave Application'].formatters || {};

frappe.listview_settings['Leave Application'].formatters = Object.assign({}, original_formatters, {
    custom_approval_status: function (value, df, doc) {
        if (!value) return '';

        const current_user = frappe.session.user;
        const hrms_status = doc.status;  // HRMS standard status field
        let display_status = value;
        let indicator_color = 'blue';

        // Contextual display: When status is "Approved HR", show "Approved GM" to non-GM users
        // GM sees actual "Approved HR" so they can click approve
        if (value === "Approved HR" && current_user !== GM_EMAIL && hrms_status !== "Approved") {
            display_status = "Approved GM";
            indicator_color = 'green';
        }
        // Determine indicator color based on status
        else if (hrms_status === "Approved") {
            indicator_color = 'green';
        } else if (value.startsWith("Approved")) {
            indicator_color = 'blue';
        } else if (value === 'Rejected') {
            indicator_color = 'red';
        } else if (value.startsWith('Pending')) {
            indicator_color = 'orange';
        }

        return `<span class="indicator-pill ${indicator_color}">${display_status}</span>`;
    }
});
