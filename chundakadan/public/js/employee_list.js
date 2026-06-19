// Employee List view enhancement — show "Setup Pending: N" badges next to
// the status indicator so HR can spot incomplete onboarding at a glance.
//
// Calls chundakadan.api.employee_setup_status.get_setup_status_bulk for
// all visible rows in one request and decorates the indicator column.

frappe.listview_settings['Employee'] = Object.assign(
    frappe.listview_settings['Employee'] || {},
    {
        onload(listview) {
            // Hook into refresh so the badge re-paints after every list reload
            const original_refresh = listview.refresh.bind(listview);
            listview.refresh = function () {
                const ret = original_refresh();
                setTimeout(() => decorate_setup_status(listview), 150);
                return ret;
            };
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
        // Find each row's DOM element and append a badge
        const $rows = $(listview.$result).find('.list-row');
        $rows.each(function () {
            const $row = $(this);
            const name = $row.attr('data-name') || $row.find('a[data-name]').attr('data-name');
            if (!name || counts[name] === undefined) return;
            const count = counts[name];
            // Remove any old badge first (refresh-safe)
            $row.find('.cdn-setup-badge').remove();
            if (count > 0) {
                const $badge = $(
                    `<span class="cdn-setup-badge" title="Onboarding setup items pending"
                        style="display:inline-block;margin-left:6px;padding:2px 8px;
                        background:#fff7e6;border:1px solid #f0ad4e;color:#b8590a;
                        border-radius:10px;font-size:11px;font-weight:600;">
                        ⚠ Setup: ${count}
                    </span>`,
                );
                $row.find('.list-row-col.ellipsis').first().append($badge);
            } else if (count === 0) {
                const $badge = $(
                    `<span class="cdn-setup-badge" title="All onboarding items complete"
                        style="display:inline-block;margin-left:6px;padding:2px 8px;
                        background:#e6f7ed;border:1px solid #0a7f3f;color:#0a7f3f;
                        border-radius:10px;font-size:11px;font-weight:600;">
                        ✓ Setup
                    </span>`,
                );
                $row.find('.list-row-col.ellipsis').first().append($badge);
            }
        });
    });
}
