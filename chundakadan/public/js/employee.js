// Adds an "Allocate Annual Leaves" entry under the standard HR Actions
// dropdown on the Employee form. Calls the chundakadan whitelisted
// method which reads Chundakadan Settings → Annual Leave Policy and
// creates Leave Allocation rows for THIS employee.
//
// Idempotent server-side: rows already covered by an existing
// allocation in the same window are skipped.

frappe.ui.form.on('Employee', {
    refresh(frm) {
        if (frm.doc.__islocal) return;
        if (frm.doc.status !== 'Active') return;

        frm.add_custom_button(
            __('Allocate Annual Leaves'),
            () => {
                frappe.confirm(
                    __('Allocate annual leaves to {0} based on Chundakadan Settings → Annual Leave Policy? Rows already allocated for the current period will be skipped.', [frm.doc.employee_name || frm.doc.name]),
                    () => {
                        frappe.call({
                            method: 'chundakadan.chundakadan.api.leave.allocate_annual_leaves_for_employee',
                            args: { employee: frm.doc.name },
                            freeze: true,
                            freeze_message: __('Allocating annual leaves...'),
                        }).then((r) => {
                            const res = r && r.message;
                            if (!res) return;
                            const created = (res.created || []).length;
                            const skipped = (res.skipped || []).length;
                            frappe.msgprint({
                                title: __('Annual Leave Allocation'),
                                indicator: created ? 'green' : 'orange',
                                message: __(
                                    'Window: {0} → {1}<br>Created: <b>{2}</b> · Skipped (already allocated): <b>{3}</b>',
                                    [res.from_date, res.to_date, created, skipped],
                                ),
                            });
                        });
                    },
                );
            },
            __('HR Actions'),
        );
    },
});
