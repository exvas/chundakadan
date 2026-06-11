// Client-side approval workflow controller shared by Expense Claim /
// Employee Advance / Payment Request. Wired from hooks.py
// (doctype_js[<DT>] entries).
//
// Mirrors the Leave Application controller:
//  - Hides the standard Submit button (Draft only; submission happens
//    via the final approve()).
//  - Adds an Approve / Reject pair to the form (Action menu) if the
//    current user is authorised at the current step.
//  - Updates an indicator bar showing approval status.

(function () {
    'use strict';

    const SUPPORTED_DOCTYPES = [
        'Expense Claim',
        'Employee Advance',
        'Payment Request',
        'Office Expense Voucher',
    ];

    function user_can_act(frm) {
        if (frappe.session.user === 'Administrator') return true;
        const admin_roles = ['System Manager', 'HR Manager'];
        if (admin_roles.some(r => frappe.user_roles.includes(r))) return true;

        if (frm.doc.current_approver === frappe.session.user) return true;

        const idx = cint(frm.doc.current_approval_index);
        const flow = frm.doc.approval_flow || [];
        if (idx >= 0 && idx < flow.length) {
            const row = flow[idx];
            if (row.approver === frappe.session.user) return true;
            if (row.approver_role && frappe.user_roles.includes(row.approver_role)) return true;
        }
        return false;
    }

    function update_indicator(frm) {
        const status = frm.doc.custom_approval_status;
        if (!status) return;
        const color_map = {
            'Pending': 'orange',
            'Partially Approved': 'orange',
            'Approved': 'green',
            'Rejected': 'red',
        };
        const color = color_map[status] || 'gray';
        frm.dashboard.set_headline_alert(
            `<div class="indicator ${color}">Approval: ${status}` +
            (frm.doc.current_approver ? ` — waiting on <b>${frm.doc.current_approver}</b>` : '') +
            '</div>'
        );
    }

    function hide_standard_submit(frm) {
        if (frm.is_new()) return;
        if (frm.doc.docstatus !== 0) return;
        // Frappe sets up the primary action async — wait a tick
        setTimeout(() => {
            try {
                if (frm.page && frm.page.btn_primary) {
                    frm.page.btn_primary.hide();
                }
                // Also hide the .primary-action button shown in some layouts
                frm.page.wrapper.find('.primary-action').filter(function () {
                    return $(this).text().trim() === __('Submit');
                }).hide();
            } catch (e) { /* swallow */ }
        }, 50);
    }

    function add_approve_reject_buttons(frm) {
        if (frm.is_new()) return;
        if (frm.doc.docstatus === 2) return;  // Cancelled
        const status = frm.doc.custom_approval_status;
        if (status === 'Approved' || status === 'Rejected') return;
        if (!user_can_act(frm)) return;
        if (!(frm.doc.approval_flow || []).length) return;

        frm.add_custom_button(__('Approve'), function () {
            frappe.confirm(
                __('Approve this {0}?', [__(frm.doctype)]),
                function () {
                    frappe.call({
                        method: 'chundakadan.chundakadan.api.expense_approval.approve',
                        args: { doctype: frm.doctype, docname: frm.doc.name },
                        freeze: true,
                        freeze_message: __('Approving...'),
                        callback: (r) => {
                            if (r.message && r.message.success) {
                                frappe.show_alert({
                                    message: __('Approved'),
                                    indicator: 'green',
                                });
                                frm.reload_doc();
                            }
                        },
                    });
                }
            );
        }, __('Actions'));

        frm.add_custom_button(__('Reject'), function () {
            frappe.prompt(
                [{
                    fieldname: 'remarks',
                    fieldtype: 'Small Text',
                    label: __('Reason for Rejection'),
                    reqd: 1,
                }],
                function (values) {
                    frappe.call({
                        method: 'chundakadan.chundakadan.api.expense_approval.reject',
                        args: {
                            doctype: frm.doctype,
                            docname: frm.doc.name,
                            remarks: values.remarks,
                        },
                        freeze: true,
                        freeze_message: __('Rejecting...'),
                        callback: (r) => {
                            if (r.message && r.message.success) {
                                frappe.show_alert({
                                    message: __('Rejected'),
                                    indicator: 'red',
                                });
                                frm.reload_doc();
                            }
                        },
                    });
                },
                __('Reject'), __('Submit')
            );
        }, __('Actions'));

        // Make Reject visually a danger button
        frm.change_custom_button_type(__('Reject'), __('Actions'), 'danger');
        frm.change_custom_button_type(__('Approve'), __('Actions'), 'primary');
    }

    function refresh(frm) {
        if (!SUPPORTED_DOCTYPES.includes(frm.doctype)) return;
        update_indicator(frm);
        hide_standard_submit(frm);
        add_approve_reject_buttons(frm);

        // Make the approval_flow child table read-only on the form
        if (frm.fields_dict.approval_flow) {
            frm.set_df_property('approval_flow', 'read_only', 1);
        }
    }

    // Register the same handler on all 3 doctypes
    SUPPORTED_DOCTYPES.forEach(function (dt) {
        frappe.ui.form.on(dt, { refresh: refresh });
    });
})();
