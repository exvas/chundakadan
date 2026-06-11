// Office Expense Voucher client controller. The shared approval UI
// (hide Submit, Approve/Reject buttons, status indicator) is delivered
// by expense_approval.js — this file ADDS only the OEV-specific bits:
//   - Auto-recompute grand_total when amount / tax_amount change
//   - "Make Payment" button on submitted-but-unpaid vouchers, opening
//     a pre-filled Payment Entry

frappe.ui.form.on('Office Expense Voucher', {
    refresh(frm) {
        if (frm.doc.docstatus === 1) {
            const outstanding = flt(frm.doc.outstanding_amount);
            if (outstanding > 0) {
                frm.add_custom_button(__('Make Payment'), function () {
                    make_payment_entry(frm);
                }, __('Create'));
                frm.page.set_inner_btn_group_as_primary(__('Create'));
            }
        }
    },

    amount(frm) {
        recompute_grand_total(frm);
    },

    tax_amount(frm) {
        recompute_grand_total(frm);
    },

    company(frm) {
        // Re-fetch the company default cost center + payable on company change
        frm.set_value('cost_center', null);
        frm.set_value('payable_account', null);
    },
});

function recompute_grand_total(frm) {
    const total = flt(frm.doc.amount) + flt(frm.doc.tax_amount);
    frm.set_value('grand_total', total);
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
