// List-view indicator override for Office Expense Voucher.
// Shows the rich `status` field (Pending Approval / Approved / etc.)
// instead of Frappe's default docstatus-based 'Draft / Submitted /
// Cancelled' indicator.

frappe.listview_settings['Office Expense Voucher'] = {
    add_fields: ['status', 'custom_approval_status', 'current_approver',
                  'docstatus', 'grand_total', 'balance_amount'],
    // Both columns ARE rendered in the row (driven by in_list_view: 1
    // on the doctype). The indicator pill below uses `status`
    // (payment lifecycle) as the headline; users can also filter by
    // 'Workflow Status' from the standard filter bar.
    get_indicator: function (doc) {
        const status_map = {
            'Draft':           ['Draft',          'red',    'status,=,Draft'],
            'Unpaid':          ['Unpaid',         'orange', 'status,=,Unpaid'],
            'Partially Paid':  ['Partially Paid', 'orange', 'status,=,Partially Paid'],
            'Paid':            ['Paid',           'green',  'status,=,Paid'],
            'Cancelled':       ['Cancelled',      'gray',   'status,=,Cancelled'],
        };
        // For a rejected workflow, fall back to showing that on the row
        if (doc.custom_approval_status === 'Rejected') {
            return ['Rejected', 'red', 'custom_approval_status,=,Rejected'];
        }
        return status_map[doc.status] || ['Draft', 'red', 'status,=,Draft'];
    },
};
