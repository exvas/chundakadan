// Employee List view enhancement — show "Setup Pending: N" / "✓ Setup"
// badges next to the row name so HR can spot incomplete onboarding at a
// glance.
//
// Calls chundakadan.api.employee_setup_status.get_setup_status_bulk for
// all visible rows in one request, then decorates the row DOM.
//
// 2026-06-22 fix: badges used to disappear on hard reload because the
// previous implementation only patched listview.refresh() at onload time
// — but on a fresh page load, the rows render BEFORE that patch had a
// chance to wrap a setTimeout. Now we:
//   1. Use Frappe's documented `refresh` hook in listview_settings, which
//      fires after every list-render cycle (initial + filter + page change).
//   2. Attach a MutationObserver to the result container as a belt-and-
//      braces — re-decorates whenever new rows are added to the DOM
//      (covers infinite-scroll, sort, and any path that bypasses refresh).
//   3. De-bounce both triggers (150ms) so we don't spam the API.

let _cdn_setup_decorate_timer = null;
let _cdn_setup_observer = null;

function schedule_decorate(listview) {
    clearTimeout(_cdn_setup_decorate_timer);
    _cdn_setup_decorate_timer = setTimeout(() => decorate_setup_status(listview), 150);
}

function attach_observer(listview) {
    // Watch the result container so we re-decorate on any DOM row change
    // (filter, scroll, sort, navigation back to list). Disconnect any
    // previous observer first — onload may fire more than once per page.
    if (_cdn_setup_observer) {
        try { _cdn_setup_observer.disconnect(); } catch (e) { /* noop */ }
    }
    const target = (listview.$result && listview.$result[0])
        || document.querySelector('.list-row-container');
    if (!target) return;
    _cdn_setup_observer = new MutationObserver(() => schedule_decorate(listview));
    _cdn_setup_observer.observe(target, { childList: true, subtree: false });
}

frappe.listview_settings['Employee'] = Object.assign(
    frappe.listview_settings['Employee'] || {},
    {
        onload(listview) {
            schedule_decorate(listview);
            attach_observer(listview);
        },
        refresh(listview) {
            // Standard Frappe listview hook — fires after every render cycle
            schedule_decorate(listview);
        },
    },
);

function decorate_setup_status(listview) {
    const rows = (listview.data || []).filter(r => r.status === 'Active');
    if (!rows.length) return;
    const names = rows.map(r => r.name);

    frappe.call({
        method: 'chundakadan.chundakadan.api.employee_setup_status.get_setup_status_bulk',
        args: { employees: JSON.stringify(names) },
        no_spinner: true,
    }).then((r) => {
        const counts = (r && r.message) || {};
        const $rows = $(listview.$result).find('.list-row');
        $rows.each(function () {
            const $row = $(this);
            const name = $row.attr('data-name') || $row.find('a[data-name]').attr('data-name');
            if (!name || counts[name] === undefined) return;
            const count = counts[name];
            // Idempotent: drop any old badge before painting the new one
            $row.find('.cdn-setup-badge').remove();
            const badge_html = count > 0
                ? `<span class="cdn-setup-badge" title="Onboarding setup items pending"
                    style="display:inline-block;margin-left:6px;padding:2px 8px;
                    background:#fff7e6;border:1px solid #f0ad4e;color:#b8590a;
                    border-radius:10px;font-size:11px;font-weight:600;">
                    ⚠ Setup: ${count}
                </span>`
                : `<span class="cdn-setup-badge" title="All onboarding items complete"
                    style="display:inline-block;margin-left:6px;padding:2px 8px;
                    background:#e6f7ed;border:1px solid #0a7f3f;color:#0a7f3f;
                    border-radius:10px;font-size:11px;font-weight:600;">
                    ✓ Setup
                </span>`;
            $row.find('.list-row-col.ellipsis').first().append($(badge_html));
        });
    });
}
