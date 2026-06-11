// List-view indicator override for Office Expense Voucher.
// Shows the rich `status` field (Pending Approval / Approved / etc.)
// instead of Frappe's default docstatus-based 'Draft / Submitted /
// Cancelled' indicator.

frappe.listview_settings['Office Expense Voucher'] = {
    add_fields: ['status', 'custom_approval_status', 'docstatus', 'grand_total'],
    get_indicator: function (doc) {
        const color_map = {
            'Draft':                ['Draft',                'red',    'status,=,Draft'],
            'Pending Approval':     ['Pending Approval',     'orange', 'status,=,Pending Approval'],
            'Partially Approved':   ['Partially Approved',   'orange', 'status,=,Partially Approved'],
            'Approved':             ['Approved',             'green',  'status,=,Approved'],
            'Unpaid':               ['Unpaid',               'orange', 'status,=,Unpaid'],
            'Paid':                 ['Paid',                 'green',  'status,=,Paid'],
            'Rejected':             ['Rejected',             'red',    'status,=,Rejected'],
            'Cancelled':            ['Cancelled',            'gray',   'status,=,Cancelled'],
        };
        return color_map[doc.status] || ['Draft', 'red', 'status,=,Draft'];
    },
};
