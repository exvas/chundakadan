// Adds an "Allocate Annual Leaves" entry under the standard HR Actions
// dropdown on the Employee form. Calls the chundakadan whitelisted
// method which reads Chundakadan Settings → Annual Leave Policy and
// creates Leave Allocation rows for THIS employee.
//
// Idempotent server-side: rows already covered by an existing
// allocation in the same window are skipped.

// Dispatch the right fix action for a pending setup key.
// Re-uses existing HR Action button clicks where possible so we don't
// duplicate dialog code.
function handle_setup_fix(frm, key) {
    if (key === 'user_account') {
        // Trigger the existing "Create User & Setup" HR Action
        const btn = frm.custom_buttons[__('Create User & Setup')];
        if (btn) { btn.click(); }
        else { frappe.show_alert({ message: __('Open HR Actions → Create User & Setup'), indicator: 'orange' }); }
        return;
    }
    if (key === 'user_permissions') {
        // Apply the standard chundakadan User Permission set to the
        // existing user — restrict to own Employee if normal staff,
        // restrict to Company in multi-company benches, skip for HR/GM.
        frappe.confirm(
            __('Apply standard user permissions for {0}? Normal staff get restricted to their own Employee + Company; managers / HR / GM stay unrestricted.',
               [frm.doc.employee_name || frm.doc.name]),
            () => {
                frappe.call({
                    method: 'chundakadan.chundakadan.api.employee_user_actions.apply_user_permissions_for_employee',
                    args: { employee: frm.doc.name },
                    freeze: true,
                }).then((r) => {
                    const res = r && r.message;
                    if (!res) return;
                    frappe.msgprint({
                        title: __('User Permissions Applied'),
                        indicator: 'green',
                        message: (res.log || []).map(l => '• ' + frappe.utils.escape_html(l)).join('<br>'),
                    });
                    frm.reload_doc();
                });
            },
        );
        return;
    }
    if (key === 'leave_allocation') {
        // Trigger the existing "Allocate Annual Leaves" HR Action
        const btn = frm.custom_buttons[__('Allocate Annual Leaves')];
        if (btn) { btn.click(); }
        else { frappe.show_alert({ message: __('Open HR Actions → Allocate Annual Leaves'), indicator: 'orange' }); }
        return;
    }
    if (key === 'leave_policy') {
        frappe.new_doc('Leave Policy Assignment', { employee: frm.doc.name });
        return;
    }
    if (key === 'shift_assignment') {
        frappe.new_doc('Shift Assignment', {
            employee: frm.doc.name,
            company: frm.doc.company,
            status: 'Active',
        });
        return;
    }
    if (key === 'salary_structure') {
        frappe.new_doc('Salary Structure Assignment', {
            employee: frm.doc.name,
            company: frm.doc.company,
        });
        return;
    }
    if (key === 'reports_to') {
        // Switch to Joining tab and focus reports_to field
        frm.scroll_to_field('reports_to');
        frappe.show_alert({ message: __('Pick a manager and Save the Employee.'), indicator: 'blue' });
        return;
    }
    frappe.show_alert({ message: __('No quick fix mapped for: {0}', [key]), indicator: 'red' });
}

// Render the "Setup Pending" banner + page-header indicator.
// Pulls from chundakadan.api.employee_setup_status.get_setup_status and
// shows HR exactly what's missing for this employee with one-click fix links.
function render_setup_status(frm) {
    if (frm.doc.__islocal || frm.doc.status !== 'Active') return;

    frappe.call({
        method: 'chundakadan.chundakadan.api.employee_setup_status.get_setup_status',
        args: { employee: frm.doc.name },
        no_spinner: true,
    }).then((r) => {
        const res = r && r.message;
        if (!res) return;
        const pending = res.checks.filter(c => !c.ok);
        const required_pending = pending.filter(c => !c.optional);

        // Page-header indicator (green / orange / red)
        if (required_pending.length === 0 && pending.length === 0) {
            frm.dashboard.set_headline_alert(
                '<div style="padding:6px 0;color:#0a7f3f;"><b>✓ Setup Complete</b> — all onboarding items done for ' +
                frappe.utils.escape_html(res.employee_name) + '.</div>',
                'green',
            );
        } else if (required_pending.length === 0) {
            // Only optional items missing — soft note
            frm.dashboard.set_headline_alert(
                '<div style="padding:6px 0;"><b>✓ Setup Complete</b> — ' + pending.length +
                ' optional item(s) not set: ' +
                pending.map(p => frappe.utils.escape_html(p.label)).join(', ') + '</div>',
                'blue',
            );
        } else {
            // Required items pending — loud orange banner with real action buttons
            const button_label = {
                user_account:      __('Create User'),
                user_permissions:  __('Apply Permissions'),
                leave_allocation:  __('Allocate Now'),
                leave_policy:      __('Assign Policy'),
                shift_assignment:  __('Assign Shift'),
                salary_structure:  __('Assign Structure'),
                reports_to:        __('Set Reports To'),
            };
            const items = pending.map(p => {
                const opt = p.optional ? ' <span style="font-size:11px;color:#888;">(optional)</span>' : '';
                const btn_label = button_label[p.key] || __('Fix');
                return `<div style="margin:6px 0;padding:8px 12px;background:#fff;border-radius:3px;display:flex;align-items:center;justify-content:space-between;">
                    <div>
                        <span style="color:#d04a02;font-size:14px;">✗</span>
                        <b>${frappe.utils.escape_html(p.label)}</b>${opt}
                    </div>
                    <button class="btn btn-sm btn-warning cdn-setup-fix-btn"
                            data-cdn-key="${p.key}"
                            style="background:#f0ad4e;color:#fff;border:none;padding:4px 14px;font-weight:600;border-radius:3px;cursor:pointer;">
                        ${btn_label} →
                    </button>
                </div>`;
            }).join('');
            const done_count = res.complete;
            const total = res.total;
            const banner = `
                <div style="background:#fff7e6;padding:14px 16px;border-left:4px solid #f0ad4e;border-radius:4px;">
                    <div style="font-size:14px;margin-bottom:8px;">
                        <b style="color:#b8590a;">⚠ ${required_pending.length} setup step(s) pending</b>
                        &nbsp;·&nbsp; <span style="color:#666;">${done_count} of ${total} done</span>
                    </div>
                    ${items}
                </div>`;
            frm.dashboard.set_headline_alert(banner, 'orange');

            // Wire button click → run the right fix action.
            // Use document-level delegation scoped by the unique class so we
            // don't depend on which jQuery wrapper the dashboard exposes
            // (frm.dashboard.wrapper vs $wrapper differs by Frappe version).
            $(document).off('click.cdnSetup').on('click.cdnSetup', '.cdn-setup-fix-btn', function (e) {
                e.preventDefault();
                const key = $(this).attr('data-cdn-key');
                if (key) handle_setup_fix(frm, key);
            });
        }

        // Page-level indicator (top breadcrumb area)
        if (required_pending.length > 0) {
            frm.page.set_indicator(
                __('Setup Pending: {0}', [required_pending.length]),
                'orange',
            );
        } else if (pending.length === 0) {
            frm.page.set_indicator(__('Setup Complete'), 'green');
        }
    });
}

frappe.ui.form.on('Employee', {
    refresh(frm) {
        if (frm.doc.__islocal) return;
        if (frm.doc.status !== 'Active') return;

        render_setup_status(frm);

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

        // Employee Transfer button — opens a new Employee Transfer
        // pre-filled with this employee, so HR doesn't have to navigate
        // away + look up the employee again. The transfer's on_submit
        // hook re-applies user permissions automatically (so promotion
        // → manager strips Employee=self perm; demotion adds it back).
        if (frm.doc.status === 'Active') {
            frm.add_custom_button(__('New Employee Transfer'), () => {
                frappe.new_doc('Employee Transfer', {
                    employee: frm.doc.name,
                    company: frm.doc.company,
                });
            }, __('HR Actions'));
        }

        // ===== Chundakadan user-management HR Actions =====
        // 4 buttons that let HR do common user-account chores without
        // touching the User doctype: create user, reset password,
        // disable on exit, re-enable on re-hire. Each opens a small
        // dialog and calls a chundakadan API method.
        const has_user = !!frm.doc.user_id;

        if (!has_user) {
            frm.add_custom_button(__('Create User & Setup'), () => {
                const default_email = frm.doc.company_email || frm.doc.personal_email || '';
                const d = new frappe.ui.Dialog({
                    title: __('Create User for {0}', [frm.doc.employee_name || frm.doc.name]),
                    fields: [
                        { fieldtype: 'Data', fieldname: 'email', label: __('Email'),
                          options: 'Email', default: default_email, reqd: 1,
                          description: __('Will become the login email. Auto-filled from Employee.company_email if set.') },
                        { fieldtype: 'Check', fieldname: 'send_welcome_email', label: __('Send welcome email with password-setup link'),
                          default: 1 },
                        { fieldtype: 'Check', fieldname: 'is_manager', label: __('This employee is a manager / approver'),
                          description: __('If checked, adds to Chundakadan Settings → Manager Details with edit + submit + approval flags. Auto-detected from designation (Manager / HOD / GM) when left unchecked.') },
                    ],
                    primary_action_label: __('Create User'),
                    primary_action(values) {
                        d.hide();
                        frappe.call({
                            method: 'chundakadan.chundakadan.api.employee_user_actions.create_user_for_employee',
                            args: {
                                employee: frm.doc.name,
                                email: values.email,
                                send_welcome_email: values.send_welcome_email ? 1 : 0,
                                is_manager: values.is_manager ? 1 : 0,
                            },
                            freeze: true,
                            freeze_message: __('Creating user...'),
                        }).then((r) => {
                            const res = r && r.message;
                            if (!res) return;
                            frappe.msgprint({
                                title: __('User Created'),
                                indicator: 'green',
                                message: __('<b>User:</b> {0}<br><br>{1}',
                                    [res.user, (res.log || []).map(l => '• ' + frappe.utils.escape_html(l)).join('<br>')]),
                            });
                            frm.reload_doc();
                        });
                    },
                });
                d.show();
            }, __('HR Actions'));
        }

        if (has_user) {
            // Reset Password
            frm.add_custom_button(__('Reset Password'), () => {
                const d = new frappe.ui.Dialog({
                    title: __('Reset password for {0}', [frm.doc.user_id]),
                    fields: [
                        { fieldtype: 'Select', fieldname: 'mode', label: __('How?'),
                          options: ['Type a new password', 'Send password-reset email'].join('\n'),
                          default: 'Type a new password', reqd: 1 },
                        { fieldtype: 'Password', fieldname: 'new_password', label: __('New Password'),
                          depends_on: "eval:doc.mode=='Type a new password'",
                          mandatory_depends_on: "eval:doc.mode=='Type a new password'",
                          description: __('Minimum 6 characters.') },
                    ],
                    primary_action_label: __('Reset'),
                    primary_action(values) {
                        d.hide();
                        const send_email = values.mode === 'Send password-reset email';
                        frappe.call({
                            method: 'chundakadan.chundakadan.api.employee_user_actions.reset_employee_password',
                            args: {
                                employee: frm.doc.name,
                                new_password: send_email ? null : values.new_password,
                                send_reset_email: send_email ? 1 : 0,
                            },
                            freeze: true,
                        }).then((r) => {
                            const res = r && r.message;
                            if (!res) return;
                            frappe.msgprint({
                                title: __('Password Reset'),
                                indicator: 'green',
                                message: (res.log || []).map(l => '• ' + frappe.utils.escape_html(l)).join('<br>'),
                            });
                        });
                    },
                });
                d.show();
            }, __('HR Actions'));

            // Check user enabled status to decide which of Disable / Re-enable to show
            frappe.db.get_value('User', frm.doc.user_id, 'enabled').then((r) => {
                const user_enabled = !!(r && r.message && r.message.enabled);

                if (user_enabled) {
                    frm.add_custom_button(__('Disable User (Exit Employee)'), () => {
                        const d = new frappe.ui.Dialog({
                            title: __('Exit {0}', [frm.doc.employee_name || frm.doc.name]),
                            fields: [
                                { fieldtype: 'Date', fieldname: 'relieving_date', label: __('Relieving Date'),
                                  default: frappe.datetime.nowdate(), reqd: 1 },
                                { fieldtype: 'Small Text', fieldname: 'reason', label: __('Reason for Leaving') },
                                { fieldtype: 'HTML', fieldname: 'warn', options:
                                    '<div style="background:#fff7e6;padding:8px;border-left:4px solid #f0ad4e;margin-top:8px;">' +
                                    '<b>This will:</b><br>' +
                                    '• Disable the user account + force-logout all sessions<br>' +
                                    '• Set Employee status = Left<br>' +
                                    '• Disable the Sales Person record (if any)<br>' +
                                    '• Remove from Chundakadan Settings → Manager Details (if present)<br><br>' +
                                    '<b>Historical data is preserved.</b> Use "Re-enable" to undo.' +
                                    '</div>' },
                            ],
                            primary_action_label: __('Disable User'),
                            primary_action(values) {
                                d.hide();
                                frappe.call({
                                    method: 'chundakadan.chundakadan.api.employee_user_actions.disable_employee_user',
                                    args: {
                                        employee: frm.doc.name,
                                        relieving_date: values.relieving_date,
                                        reason: values.reason || '',
                                    },
                                    freeze: true,
                                    freeze_message: __('Disabling user...'),
                                }).then((r) => {
                                    const res = r && r.message;
                                    if (!res) return;
                                    frappe.msgprint({
                                        title: __('Employee Exited'),
                                        indicator: 'orange',
                                        message: (res.log || []).map(l => '• ' + frappe.utils.escape_html(l)).join('<br>'),
                                    });
                                    frm.reload_doc();
                                });
                            },
                        });
                        d.show();
                    }, __('HR Actions'));
                } else {
                    frm.add_custom_button(__('Re-enable User'), () => {
                        frappe.confirm(
                            __('Re-activate {0}? This re-enables the user, sets Employee status back to Active, and re-creates the Sales Person if applicable.',
                               [frm.doc.employee_name || frm.doc.name]),
                            () => {
                                frappe.call({
                                    method: 'chundakadan.chundakadan.api.employee_user_actions.enable_employee_user',
                                    args: { employee: frm.doc.name },
                                    freeze: true,
                                }).then((r) => {
                                    const res = r && r.message;
                                    if (!res) return;
                                    frappe.msgprint({
                                        title: __('User Re-enabled'),
                                        indicator: 'green',
                                        message: (res.log || []).map(l => '• ' + frappe.utils.escape_html(l)).join('<br>'),
                                    });
                                    frm.reload_doc();
                                });
                            },
                        );
                    }, __('HR Actions'));
                }
            });
        }
    },
});
