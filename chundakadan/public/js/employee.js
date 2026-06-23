// Adds an "Allocate Annual Leaves" entry under the standard HR Actions
// dropdown on the Employee form. Calls the chundakadan whitelisted
// method which reads Chundakadan Settings → Annual Leave Policy and
// creates Leave Allocation rows for THIS employee.
//
// Idempotent server-side: rows already covered by an existing
// allocation in the same window are skipped.

// Single-pane Employee Setup Dashboard — opens a big read+act dialog
// summarising User / Permissions / Sales Person / Geofence / Leave /
// Shift / Salary / Reports To / Manager Details for one employee.
// Each section has a ✓/✗ pill + an action button that routes back to
// the same handlers the Setup Pending banner uses, so the fix flows
// are shared.
function show_setup_dashboard(frm) {
    frappe.call({
        method: 'chundakadan.chundakadan.api.employee_user_actions.get_employee_dashboard',
        args: { employee: frm.doc.name },
        freeze: true,
        freeze_message: __('Loading dashboard...'),
    }).then((r) => {
        const data = r && r.message;
        if (!data) return;
        render_setup_dashboard_dialog(frm, data);
    });
}

function _pill(ok, label_ok, label_warn) {
    const bg = ok ? '#e6f7ed' : '#fff7e6';
    const fg = ok ? '#0a7f3f' : '#b8590a';
    const border = ok ? '#0a7f3f' : '#f0ad4e';
    const text = ok ? (label_ok || '✓ OK') : (label_warn || '⚠ Action needed');
    return `<span style="display:inline-block;padding:2px 10px;background:${bg};color:${fg};
        border:1px solid ${border};border-radius:10px;font-size:11px;font-weight:600;">${text}</span>`;
}

function render_setup_dashboard_dialog(frm, data) {
    const s = data.sections;
    const esc = frappe.utils.escape_html;

    const section_html = [];

    // 1. User Account
    const ua = s.user_account;
    section_html.push(`
        <div class="cdn-dash-sec">
            <div class="cdn-dash-head">👤 User Account ${_pill(ua.ok)}</div>
            <div class="cdn-dash-body">
                ${ua.user_id ? `Login: <b>${esc(ua.user_id)}</b> ${ua.enabled ? '(enabled)' : '<span style="color:#d04a02;">(DISABLED)</span>'}<br>
                Last login: ${esc(ua.last_login || 'never')}<br>
                Roles: ${esc((ua.roles || []).join(', ') || 'none')}` : '<i>No User linked yet — click Create User & Setup below.</i>'}
            </div>
            <div class="cdn-dash-actions">
                ${!ua.user_id ? `<button class="btn btn-sm cdn-dash-btn" data-action="user_account">Create User & Setup</button>` : ''}
                ${ua.user_id && ua.enabled ? `<button class="btn btn-sm cdn-dash-btn" data-action="reset_password">Reset Password</button>` : ''}
                ${ua.user_id && ua.enabled ? `<button class="btn btn-sm cdn-dash-btn" data-action="disable_user">Disable User</button>` : ''}
                ${ua.user_id && !ua.enabled ? `<button class="btn btn-sm cdn-dash-btn" data-action="enable_user">Re-enable</button>` : ''}
            </div>
        </div>`);

    // 2. User Permissions
    const up = s.user_permissions;
    let up_detail = '';
    if (ua.user_id) {
        const lines = [];
        if (up.needs_employee_perm) lines.push(up.has_employee_perm ? '✓ Employee = self' : '✗ Missing Employee=self');
        if (up.needs_company_perm) lines.push(up.has_company_perm ? '✓ Company restriction' : '✗ Missing Company');
        if (up.stale_employee_perm) lines.push('✗ Stale Employee=self perm (manager/HR shouldn\'t have)');
        if (!up.needs_employee_perm && !up.needs_company_perm) lines.push('No restrictions needed (manager/HR/GM, single-company)');
        up_detail = lines.join('<br>');
    } else {
        up_detail = '<i>No user linked — create user first</i>';
    }
    section_html.push(`
        <div class="cdn-dash-sec">
            <div class="cdn-dash-head">🔐 User Permissions ${_pill(up.ok)}</div>
            <div class="cdn-dash-body">${up_detail}</div>
            <div class="cdn-dash-actions">
                ${ua.user_id && !up.ok ? `<button class="btn btn-sm cdn-dash-btn" data-action="user_permissions">Apply / Clean</button>` : ''}
            </div>
        </div>`);

    // 3. Sales Person
    const sp = s.sales_person;
    if (sp.applicable) {
        const sp_detail = sp.name
            ? `Sales Person: <b>${esc(sp.name)}</b> ${sp.enabled ? '(enabled)' : '<span style="color:#d04a02;">(disabled)</span>'}<br>MOP rows: ${sp.mop_rows}`
            : '✗ No Sales Person record';
        section_html.push(`
            <div class="cdn-dash-sec">
                <div class="cdn-dash-head">💼 Sales Person ${_pill(sp.ok)}</div>
                <div class="cdn-dash-body">${sp_detail}</div>
                <div class="cdn-dash-actions">
                    ${!sp.ok ? `<button class="btn btn-sm cdn-dash-btn" data-action="sales_person">Setup Sales Person</button>` : ''}
                </div>
            </div>`);
    }

    // 4. Geofence (Shift Assignment.shift_location)
    const gf = s.geofence;
    let gf_detail = '';
    if (gf.applicable) {
        gf_detail = gf.active_assignments.map(sa =>
            `${esc(sa.name)}: shift_type=${esc(sa.shift_type || '?')}, geofence=<b>${esc(sa.shift_location || '<NONE — field staff>')}</b>`
        ).join('<br>');
        gf_detail += `<br><br>Expected for this dept (${data.is_sales_dept ? 'Sales/Marketing' : 'Office'}): <b>${esc(gf.expected || '<NONE — field staff>')}</b>`;
    } else {
        gf_detail = '<i>No active Shift Assignment — create one first via Setup Pending → Assign Shift</i>';
    }
    const loc_opts = ['', ...(gf.available_locations || [])].map(l =>
        `<option value="${esc(l)}">${l ? esc(l) : '(none — field staff, no geofence)'}</option>`
    ).join('');
    section_html.push(`
        <div class="cdn-dash-sec">
            <div class="cdn-dash-head">📍 Geofence ${_pill(gf.ok, '✓ Matches policy', '⚠ Mismatch — set correctly')}</div>
            <div class="cdn-dash-body">${gf_detail}</div>
            ${gf.applicable ? `<div class="cdn-dash-actions">
                <select class="form-control cdn-geofence-pick" style="display:inline-block;width:auto;">${loc_opts}</select>
                <button class="btn btn-sm cdn-dash-btn" data-action="geofence_apply">Apply</button>
            </div>` : ''}
            <div style="font-size:11px;color:#888;margin-top:4px;">After change, ask the employee to LOG OUT + LOG BACK IN on mobile so cached config refreshes.</div>
        </div>`);

    // 5. Leave Allocation
    const la = s.leave_allocation;
    section_html.push(`
        <div class="cdn-dash-sec">
            <div class="cdn-dash-head">📅 Leave Allocation ${_pill(la.ok, `✓ ${la.count} active`, '⚠ No allocations')}</div>
            <div class="cdn-dash-body">${la.ok ? `${la.count} allocation(s) covering today` : '✗ Employee can\'t apply for leave without an allocation'}</div>
            <div class="cdn-dash-actions">
                ${!la.ok ? `<button class="btn btn-sm cdn-dash-btn" data-action="leave_allocation">Allocate Annual Leaves</button>` : ''}
            </div>
        </div>`);

    // 6. Shift Assignment
    const sa = s.shift_assignment;
    section_html.push(`
        <div class="cdn-dash-sec">
            <div class="cdn-dash-head">⏰ Shift Assignment ${_pill(sa.ok, `✓ ${sa.count} active`, '⚠ None')}</div>
            <div class="cdn-dash-body">${sa.ok ? `Shifts: ${esc((sa.shifts || []).join(', '))}` : 'No active Shift Assignment'}</div>
            <div class="cdn-dash-actions">
                ${!sa.ok ? `<button class="btn btn-sm cdn-dash-btn" data-action="shift_assignment">Assign Shift</button>` : ''}
            </div>
        </div>`);

    // 7. Salary Structure
    const ss = s.salary_structure;
    section_html.push(`
        <div class="cdn-dash-sec">
            <div class="cdn-dash-head">💰 Salary Structure ${_pill(ss.ok)}</div>
            <div class="cdn-dash-body">${ss.ok ? `<b>${esc(ss.structure)}</b><br>Base: ₹${esc(String(ss.base || 0))} · from ${esc(ss.from_date || '')}` : '✗ Not assigned'}</div>
            <div class="cdn-dash-actions">
                ${!ss.ok ? `<button class="btn btn-sm cdn-dash-btn" data-action="salary_structure">Assign Structure</button>` : ''}
            </div>
        </div>`);

    // 8. Reports To — inline picker, applies via dashboard_update
    const rt = s.reports_to;
    section_html.push(`
        <div class="cdn-dash-sec">
            <div class="cdn-dash-head">👔 Reports To ${_pill(rt.ok, '✓ Set', 'ℹ Not set')}</div>
            <div class="cdn-dash-body">${rt.ok ? `Currently reports to: <b>${esc(rt.reports_to_name || rt.reports_to)}</b>` : '<i>Optional — set if this person has a manager</i>'}</div>
            <div class="cdn-dash-actions">
                <input type="text" class="form-control cdn-reports-to" style="display:inline-block;width:260px;" placeholder="Type employee name or ID to change..." />
                <button class="btn btn-sm cdn-dash-btn" data-action="reports_to_apply">Apply</button>
                ${rt.ok ? `<button class="btn btn-sm" data-action="reports_to_clear" style="background:#fff;border:1px solid #ccc;">Clear</button>` : ''}
            </div>
        </div>`);

    // Inline shift type change — only if there's an active SA already
    if (sa.ok) {
        section_html.push(`
            <div class="cdn-dash-sec">
                <div class="cdn-dash-head">🔄 Change Shift Type</div>
                <div class="cdn-dash-body">Cancels current active Shift Assignment + creates a new one with the chosen shift type. Geofence (shift_location) is preserved.</div>
                <div class="cdn-dash-actions">
                    <input type="text" class="form-control cdn-shift-type" style="display:inline-block;width:260px;" placeholder="Type Shift Type name..." />
                    <button class="btn btn-sm cdn-dash-btn" data-action="shift_type_apply">Apply New Shift</button>
                </div>
            </div>`);
    }

    // 9. Manager Details — add/remove toggle
    const md = s.manager_details;
    section_html.push(`
        <div class="cdn-dash-sec">
            <div class="cdn-dash-head">🏢 Manager Details ${_pill(md.in_table || !md.expected, md.in_table ? '✓ Listed' : 'Not applicable', '⚠ Should be listed')}</div>
            <div class="cdn-dash-body">${md.in_table
                ? `In Chundakadan Settings → Manager Details<br>allow_edit=${md.allow_edit} · allow_submit=${md.allow_submit} · workflow_approval=${md.workflow_approval}`
                : (md.expected ? '✗ Designation suggests manager role — not in manager_details' : '<i>Not applicable for this designation</i>')}</div>
            <div class="cdn-dash-actions">
                ${md.in_table
                    ? `<button class="btn btn-sm" data-action="manager_details_remove" style="background:#fff;border:1px solid #ccc;">Remove from Manager Details</button>`
                    : `<button class="btn btn-sm cdn-dash-btn" data-action="manager_details_add">Add to Manager Details</button>`}
            </div>
        </div>`);

    // Toggle Sales Person enable/disable
    if (sp.applicable && sp.name) {
        section_html.push(`
            <div class="cdn-dash-sec">
                <div class="cdn-dash-head">🔁 Toggle Sales Person Active</div>
                <div class="cdn-dash-body">Current: <b>${sp.enabled ? 'enabled' : 'disabled'}</b>. Flip the enabled flag on the Sales Person record (kept historically either way).</div>
                <div class="cdn-dash-actions">
                    <button class="btn btn-sm cdn-dash-btn" data-action="sales_person_toggle">${sp.enabled ? 'Disable' : 'Enable'} Sales Person</button>
                </div>
            </div>`);
    }

    const css = `
        <style>
        .cdn-dash-sec { padding:10px 12px; margin-bottom:10px; background:#fff;
            border:1px solid #e0e0e0; border-radius:6px; }
        .cdn-dash-head { font-weight:600; font-size:14px; margin-bottom:6px;
            display:flex; justify-content:space-between; align-items:center; gap:8px; }
        .cdn-dash-body { font-size:12px; color:#444; margin-bottom:8px; line-height:1.55; }
        .cdn-dash-actions { display:flex; gap:6px; align-items:center; flex-wrap:wrap; }
        .cdn-dash-btn { background:#f0ad4e !important; color:#fff !important;
            border:none !important; font-weight:600; }
        .cdn-dash-btn:hover { background:#e8a14a !important; }
        </style>`;

    const d = new frappe.ui.Dialog({
        title: __('Setup Dashboard — {0}', [data.employee_name]),
        size: 'large',
        fields: [{
            fieldtype: 'HTML', fieldname: 'body',
            options: css + `<div style="background:#f7f8fa;padding:12px;border-radius:6px;">
                <div style="font-size:13px;margin-bottom:10px;">
                    <b>${esc(data.employee_name)}</b> · ${esc(data.designation || '?')} · ${esc(data.department || '?')}
                </div>
                ${section_html.join('')}
            </div>`,
        }],
        primary_action_label: __('Close'),
        primary_action: () => d.hide(),
    });
    d.show();

    // Wire dashboard action buttons — most route to the existing
    // handle_setup_fix() dispatcher (same fixes the banner uses).
    // Geofence has its own apply-with-dropdown flow.
    d.$wrapper.on('click', '.cdn-dash-btn', function () {
        const action = $(this).data('action');
        if (action === 'reset_password') {
            const btn = frm.custom_buttons[__('Reset Password')];
            if (btn) { d.hide(); btn.click(); }
            return;
        }
        if (action === 'disable_user') {
            const btn = frm.custom_buttons[__('Disable User (Exit Employee)')];
            if (btn) { d.hide(); btn.click(); }
            return;
        }
        if (action === 'enable_user') {
            const btn = frm.custom_buttons[__('Re-enable User')];
            if (btn) { d.hide(); btn.click(); }
            return;
        }
        // Inline editors — route through generic dashboard_update endpoint
        const inline_actions = {
            reports_to_apply:        { dash: 'reports_to',          val: () => d.$wrapper.find('.cdn-reports-to').val(),  confirm: 'Set reports_to?' },
            reports_to_clear:        { dash: 'reports_to',          val: () => '',                                         confirm: 'Clear reports_to?' },
            shift_type_apply:        { dash: 'shift_type',          val: () => d.$wrapper.find('.cdn-shift-type').val(),   confirm: 'Cancel current Shift Assignment + create new with this shift type?' },
            sales_person_toggle:     { dash: 'sales_person_toggle', val: () => null,                                       confirm: 'Toggle Sales Person enabled flag?' },
            manager_details_add:     { dash: 'manager_details_add', val: () => null,                                       confirm: 'Add to Chundakadan Settings → manager_details with all 3 flags ON?' },
            manager_details_remove:  { dash: 'manager_details_remove', val: () => null,                                    confirm: 'Remove from manager_details?' },
        };
        if (inline_actions[action]) {
            const cfg = inline_actions[action];
            frappe.confirm(__(cfg.confirm), () => {
                frappe.call({
                    method: 'chundakadan.chundakadan.api.employee_user_actions.dashboard_update',
                    args: { employee: frm.doc.name, action: cfg.dash, value: cfg.val() },
                    freeze: true,
                }).then((r) => {
                    const res = r && r.message;
                    frappe.msgprint({
                        title: __('Updated'),
                        indicator: 'green',
                        message: ((res && res.log) || []).map(l => '• ' + frappe.utils.escape_html(l)).join('<br>'),
                    });
                    d.hide();
                    frm.reload_doc();
                });
            });
            return;
        }
        if (action === 'geofence_apply') {
            const picked = d.$wrapper.find('.cdn-geofence-pick').val();
            frappe.confirm(
                __('Apply geofence "{0}" to all active Shift Assignments? Employee must log out + back in on mobile after this.',
                   [picked || '(none — field staff)']),
                () => {
                    frappe.call({
                        method: 'chundakadan.chundakadan.api.employee_user_actions.apply_geofence_for_employee',
                        args: { employee: frm.doc.name, shift_location: picked },
                        freeze: true,
                    }).then((r) => {
                        const res = r && r.message;
                        if (!res) return;
                        frappe.msgprint({
                            title: __('Geofence Applied'),
                            indicator: 'green',
                            message: (res.log || []).map(l => '• ' + frappe.utils.escape_html(l)).join('<br>'),
                        });
                        d.hide();
                        frm.reload_doc();
                    });
                },
            );
            return;
        }
        // Everything else → existing dispatcher (handles 7 keys)
        d.hide();
        handle_setup_fix(frm, action);
    });
}

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
    if (key === 'sales_person') {
        frappe.confirm(
            __('Create / repair Sales Person record + MOP mapping for {0}? Required for the field_sales mobile app to log customer visits.',
               [frm.doc.employee_name || frm.doc.name]),
            () => {
                frappe.call({
                    method: 'chundakadan.chundakadan.api.employee_user_actions.apply_sales_person_setup_for_employee',
                    args: { employee: frm.doc.name },
                    freeze: true,
                }).then((r) => {
                    const res = r && r.message;
                    if (!res) return;
                    frappe.msgprint({
                        title: __('Sales Person Ready'),
                        indicator: 'green',
                        message: '<b>Sales Person:</b> ' + frappe.utils.escape_html(res.sales_person || '?') + '<br><br>'
                            + (res.log || []).map(l => '• ' + frappe.utils.escape_html(l)).join('<br>'),
                    });
                    frm.reload_doc();
                });
            },
        );
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
                sales_person:      __('Setup Sales Person'),
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

        // Setup Dashboard — single-pane view of everything assigned to
        // this employee (user account, permissions, sales person, geofence,
        // leave allocation, shift, salary structure, reports_to, manager
        // details). Replaces hunting across 6+ doctypes when HR wants to
        // see "what's set up for this person" or fix a gap. Each section
        // has ✓/✗ + an inline action button (Set Geofence / Apply Perms /
        // Allocate Leaves / etc.) — every fix routes to the same handlers
        // the Setup Pending banner uses, so behavior stays consistent.
        if (frm.doc.status === 'Active') {
            frm.add_custom_button(__('Setup Dashboard'), () => {
                show_setup_dashboard(frm);
            }, __('HR Actions'));
        }

        // Setup Sales Person — fixes the field_sales mobile app's
        // "Missing required field: sales_person" error for sales/marketing
        // employees whose User account was created without going through
        // Create User & Setup. Visible only when this employee is in a
        // sales-dept and either has no Sales Person OR has a disabled one.
        const dept = (frm.doc.department || '').toLowerCase();
        const is_sales = dept.includes('sales') || dept.includes('marketing');
        if (is_sales) {
            frappe.db.get_value('Sales Person', { employee: frm.doc.name },
                                  ['name', 'enabled']).then((r) => {
                const sp = r && r.message;
                const needs = !sp || !sp.name || !sp.enabled;
                if (needs) {
                    frm.add_custom_button(__('Setup Sales Person'), () => {
                        handle_setup_fix(frm, 'sales_person');
                    }, __('HR Actions'));
                }
            });
        }

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
