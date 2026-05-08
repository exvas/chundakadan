//code written by niranjana nir
// List view customization for Leave Application - shows contextual approval status

frappe.listview_settings['Leave Application'] = frappe.listview_settings['Leave Application'] || {};

// Store original formatters
const original_formatters = frappe.listview_settings['Leave Application'].formatters || {};

frappe.listview_settings['Leave Application'].formatters = Object.assign({}, original_formatters, {
    custom_approval_status: function (value, df, doc) {
        if (!value) return '';

        const hrms_status = doc.status;  // HRMS standard status field
        let indicator_color = 'blue';

        // Determine indicator color based on status
        // Everyone sees the actual stored status value
        if (hrms_status === "Approved") {
            indicator_color = 'green';
        } else if (value.startsWith("Approved")) {
            indicator_color = 'blue';
        } else if (value === 'Rejected') {
            indicator_color = 'red';
        } else if (value.startsWith('Pending')) {
            indicator_color = 'orange';
        }

        return `<span class="indicator-pill ${indicator_color}">${__(value)}</span>`;
    }
});
