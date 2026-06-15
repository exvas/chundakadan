// Auto-detect transfer type from the (old → new) department change and
// pre-fill the Employee Transfer Detail child rows so HR can review
// before submit. The server-side hook
// `chundakadan.doc_events.employee_transfer.apply_chundakadan_side_effects`
// then runs all the actual side-effects on submit.

frappe.ui.form.on('Employee Transfer', {
    refresh: function (frm) {
        if (!frm.is_new() && frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Preview Side-Effects'), function () {
                _show_preview(frm);
            }, __('Actions'));
        }
        if (frm.doc.docstatus === 1) {
            frm.dashboard.add_indicator(
                __('Side-effects auto-applied'), 'green');
            // Cancel-prevention notice — server also hard-blocks
            // before_cancel, this just sets the expectation up front.
            frm.dashboard.add_comment(
                __('🚫 Cancel disabled — cancelling would not undo the '
                + 'side-effects. To undo this transfer, create a NEW '
                + 'Employee Transfer in the REVERSE direction '
                + '(e.g. Sales → Billing) and submit it.'),
                'orange',
                true
            );
        }
    },

    department: function (frm) {
        if (!frm.doc.employee || !frm.doc.department) return;
        _detect_and_autofill(frm);
    },

    new_company: function (frm) {
        if (frm.doc.new_company && frm.doc.new_company !== frm.doc.company) {
            frm.set_value('custom_transfer_type', 'Company Change');
        }
    },
});


function _is_sales(dept) {
    return dept && /sales|marketing/i.test(dept);
}


function _detect_and_autofill(frm) {
    frappe.db.get_value('Employee', frm.doc.employee, 'department')
        .then((r) => {
            const old_dept = r && r.message && r.message.department;
            const new_dept = frm.doc.department;
            const old_sales = _is_sales(old_dept);
            const new_sales = _is_sales(new_dept);

            let t = 'Other';
            if (frm.doc.new_company && frm.doc.new_company !== frm.doc.company) {
                t = 'Company Change';
            } else if (!old_sales && new_sales) {
                t = 'To Sales & Marketing';
            } else if (old_sales && !new_sales) {
                t = 'From Sales & Marketing';
            } else if (old_dept !== new_dept) {
                t = 'Office to Office';
            }

            frm.set_value('custom_transfer_type', t);
            _autofill_details(frm, old_dept, new_dept);
        });
}


function _autofill_details(frm, old_dept, new_dept) {
    if (!frm.fields_dict.transfer_details) return;
    // Don't wipe rows HR may have added — only add the Department row
    // if it's not already there.
    const existing_props = (frm.doc.transfer_details || [])
        .map((r) => r.property);
    if (!existing_props.includes('Department') && old_dept !== new_dept) {
        const row = frm.add_child('transfer_details');
        row.property = 'Department';
        row.current = old_dept || '';
        row.new = new_dept || '';
        row.fieldname = 'department';
        frm.refresh_field('transfer_details');
    }
}


function _show_preview(frm) {
    if (!frm.doc.custom_transfer_type) {
        frappe.msgprint(__('Pick a New Department first.'));
        return;
    }
    const t = frm.doc.custom_transfer_type;
    const previews = {
        'To Sales & Marketing': [
            'Create / re-enable Sales Person record linked to this employee',
            'Add Cash + Cheque rows to Chundakadan Settings → MOP Mapping',
            'Clear shift_location on active Shift Assignment (becomes field staff — no geofence)',
            'Switch Salary Structure → CDN Sales Executive Structure (base preserved)',
            'Switch Role Profile → CDN Sales Executive (User\'s roles change)',
            'Update leave_approver → Sales HOD',
        ],
        'From Sales & Marketing': [
            'Disable Sales Person (history kept, customers stay linked)',
            'Keep historical MOP Mapping rows (audit)',
            'Set shift_location=HOD on active Shift Assignment (becomes office staff — geofenced)',
            'Switch Salary Structure → matching office structure',
            'Switch Role Profile → matching CDN role profile',
            'Update leave_approver based on new department',
        ],
        'Office to Office': [
            'Switch Salary Structure if dept-mapping changes',
            'Switch Role Profile',
            'Update leave_approver if HOD changes',
        ],
        'Company Change': [
            'Standard ERPNext company change (no Chundakadan extras).',
        ],
        'Other': ['No Chundakadan side-effects will run.'],
    };
    const lines = (previews[t] || []).map(
        (s) => `<li>${frappe.utils.escape_html(s)}</li>`).join('');
    frappe.msgprint({
        title: __('Side-effects on Submit ({0})', [t]),
        message: `<ul>${lines}</ul>`
                 + `<p><i>Each step will be logged as a Comment on this `
                 + `transfer for audit.</i></p>`,
        indicator: 'blue',
    });
}
