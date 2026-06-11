// Office Expense Voucher client controller.
// The shared approval UI (hide Submit, Approve/Reject buttons, status
// indicator) is delivered by expense_approval.js — this file ADDS
// only the OEV-specific bits:
//   - Recompute totals when any line / tax changes
//   - 'Make Payment' button on submitted + unpaid (deferred-mode) vouchers
//   - Auto-fill Paid From / Cost Center / Payable Account from
//     Chundakadan Settings on a fresh form (paid_from blank case)

frappe.ui.form.on('Office Expense Voucher', {
    setup(frm) {
        // Filter Paid From to only Bank / Cash accounts of the selected company
        frm.set_query('paid_from', () => ({
            filters: {
                company: frm.doc.company,
                is_group: 0,
                account_type: ['in', ['Bank', 'Cash']],
                disabled: 0,
            },
        }));
        // Filter Payable Account to non-group Liability accounts on the company,
        // excluding account_type='Payable' (we don't want party-based ones)
        frm.set_query('payable_account', () => ({
            filters: {
                company: frm.doc.company,
                is_group: 0,
                root_type: 'Liability',
                disabled: 0,
            },
        }));
        // Expense lines: only Expense-type leaf accounts of this company
        frm.set_query('expense_account', 'items', () => ({
            filters: {
                company: frm.doc.company,
                is_group: 0,
                root_type: 'Expense',
                disabled: 0,
            },
        }));
        frm.set_query('cost_center', 'items', () => ({
            filters: {
                company: frm.doc.company,
                is_group: 0,
                disabled: 0,
            },
        }));
    },

    onload(frm) {
        if (frm.is_new() && frm.doc.company) {
            apply_company_defaults(frm);
        }
    },

    refresh(frm) {
        // Make Payment button — only when submitted, no paid_from set
        // (i.e. deferred-payment mode via Payable Account), still unpaid.
        if (frm.doc.docstatus === 1
            && !frm.doc.paid_from
            && !frm.doc.is_reimbursable
            && frm.doc.status === 'Unpaid') {
            frm.add_custom_button(__('Make Payment'), function () {
                make_payment_entry(frm);
            }, __('Create'));
            frm.page.set_inner_btn_group_as_primary(__('Create'));
        }
        recompute_totals(frm);

    },

    company(frm) {
        if (frm.doc.docstatus !== 0) return;
        // Clear company-tied fields, then re-apply defaults for the new company
        frm.set_value('paid_from', null);
        frm.set_value('payable_account', null);
        (frm.doc.items || []).forEach(it => {
            frappe.model.set_value(it.doctype, it.name, 'cost_center', null);
        });
        if (frm.doc.company) {
            apply_company_defaults(frm);
        }
    },

    is_reimbursable(frm) {
        // If marked reimbursable, paid_from doesn't apply (Cr goes to
        // employee payable). Clear it for clarity.
        if (frm.doc.is_reimbursable) {
            frm.set_value('paid_from', null);
        }
    },
});

frappe.ui.form.on('Office Expense Voucher Item', {
    amount(frm) { recompute_totals(frm); },
    tax_amount(frm) { recompute_totals(frm); },
    items_remove(frm) { recompute_totals(frm); },

    items_add(frm, cdt, cdn) {
        // Auto-fill the cost center on each new line from
        // the per-company default (resolved server-side).
        if (!frm.doc.company) return;
        const row = locals[cdt][cdn];
        if (row.cost_center) return;
        frappe.call({
            method: 'chundakadan.chundakadan.doctype.office_expense_voucher.office_expense_voucher.get_company_defaults',
            args: { company: frm.doc.company },
        }).then(r => {
            const d = (r && r.message) || {};
            if (d.cost_center && !row.cost_center) {
                frappe.model.set_value(cdt, cdn, 'cost_center', d.cost_center);
            }
        });
    },
});

function apply_company_defaults(frm) {
    frappe.call({
        method: 'chundakadan.chundakadan.doctype.office_expense_voucher.office_expense_voucher.get_company_defaults',
        args: { company: frm.doc.company },
    }).then(r => {
        const d = (r && r.message) || {};
        if (!frm.doc.paid_from && d.paid_from) {
            frm.set_value('paid_from', d.paid_from);
        }
        if (!frm.doc.payable_account && d.payable_account) {
            frm.set_value('payable_account', d.payable_account);
        }
        if (d.cost_center) {
            (frm.doc.items || []).forEach(it => {
                if (!it.cost_center) {
                    frappe.model.set_value(it.doctype, it.name,
                        'cost_center', d.cost_center);
                }
            });
        }
    });
}

function recompute_totals(frm) {
    let subtotal = 0;
    let total_tax = 0;
    (frm.doc.items || []).forEach(row => {
        subtotal += flt(row.amount);
        total_tax += flt(row.tax_amount);
    });
    frm.set_value('subtotal', subtotal);
    frm.set_value('total_tax', total_tax);
    frm.set_value('grand_total', subtotal + total_tax);
}

function make_payment_entry(frm) {
    frappe.call({
        method: 'chundakadan.chundakadan.doctype.office_expense_voucher.office_expense_voucher.make_payment_entry',
        args: { source_name: frm.doc.name },
        freeze: true,
        freeze_message: __('Building Payment Entry...'),
        callback: function (r) {
            if (!r.message) return;
            const pe = frappe.model.sync(r.message)[0];
            frappe.set_route('Form', 'Payment Entry', pe.name);
        },
    });
}
