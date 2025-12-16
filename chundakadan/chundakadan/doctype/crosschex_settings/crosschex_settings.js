// Copyright (c) 2025, Chundakadan and contributors
// For license information, please see license.txt

frappe.ui.form.on('Crosschex Settings', {
    refresh: function(frm) {
        // Form refresh handler
    }
});

// Child table: CrossChex API Configuration
frappe.ui.form.on('CrossChex API Configuration', {
    api_configurations_add: function(frm, cdt, cdn) {
        // Set default values for new row
        let row = locals[cdt][cdn];
        if (!row.api_url) {
            frappe.model.set_value(cdt, cdn, 'connection_status', 'Not Tested');
        }
    },

    // Handle Test Connection button click
    test_connection: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        test_individual_connection(frm, row);
    },

    // Handle Sync Now button click
    sync_now: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        sync_individual_device(frm, row);
    },

    // Handle Full Resync button click
    full_resync: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        full_resync_device(frm, row);
    }
});

function test_individual_connection(frm, config_row) {
    if (!config_row.api_url || !config_row.api_key || !config_row.api_secret) {
        frappe.msgprint({
            title: __('Missing Information'),
            message: __('Please fill in API URL, API Key, and API Secret before testing.'),
            indicator: 'orange'
        });
        return;
    }

    // Check if the document is saved
    if (!config_row.name || config_row.name.startsWith('new-')) {
        frappe.msgprint({
            title: __('Save Required'),
            message: __('Please save the document first before testing the connection. Password fields are only stored after saving.'),
            indicator: 'orange'
        });
        return;
    }

    frappe.call({
        method: 'chundakadan.chundakadan.doctype.crosschex_settings.crosschex_settings.test_individual_api_config',
        args: {
            api_url: config_row.api_url,
            api_key: config_row.api_key,
            config_row_name: config_row.name,
            config_name: config_row.configuration_name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint({
                    title: __('Success'),
                    message: __('Connection to {0} successful!', [config_row.configuration_name || config_row.api_url]),
                    indicator: 'green'
                });

                // Update the row's connection status
                frappe.model.set_value(config_row.doctype, config_row.name, 'connection_status', 'Connected');
                frappe.model.set_value(config_row.doctype, config_row.name, 'token', r.message.token);
                if (r.message.expires) {
                    frappe.model.set_value(config_row.doctype, config_row.name, 'token_expires', r.message.expires);
                }
                frappe.model.set_value(config_row.doctype, config_row.name, 'last_token_generated', frappe.datetime.now_datetime());

                frm.refresh_field('api_configurations');
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message ? r.message.error : __('Connection failed'),
                    indicator: 'red'
                });

                // Update the row's connection status
                frappe.model.set_value(config_row.doctype, config_row.name, 'connection_status', 'Error');
                frm.refresh_field('api_configurations');
            }
        }
    });
}

function sync_individual_device(frm, config_row) {
    if (!config_row.api_url || !config_row.api_key || !config_row.api_secret) {
        frappe.msgprint({
            title: __('Missing Information'),
            message: __('Please fill in API URL, API Key, and API Secret before syncing.'),
            indicator: 'orange'
        });
        return;
    }

    // Check if the document is saved
    if (!config_row.name || config_row.name.startsWith('new-')) {
        frappe.msgprint({
            title: __('Save Required'),
            message: __('Please save the document first before syncing.'),
            indicator: 'orange'
        });
        return;
    }

    // Show progress indicator
    frappe.show_alert({
        message: __('Starting sync for {0}...', [config_row.configuration_name || config_row.api_url]),
        indicator: 'blue'
    });

    frappe.call({
        method: 'chundakadan.chundakadan.doctype.crosschex_settings.crosschex_settings.sync_individual_device',
        args: {
            api_url: config_row.api_url,
            api_key: config_row.api_key,
            config_row_name: config_row.name,
            config_name: config_row.configuration_name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint({
                    title: __('Success'),
                    message: __('Sync completed for {0}! Processed {1} records.',
                        [config_row.configuration_name || config_row.api_url, r.message.processed || 0]),
                    indicator: 'green'
                });

                // Update sync status fields
                frappe.model.set_value(config_row.doctype, config_row.name, 'last_sync_time', frappe.datetime.now_datetime());
                frappe.model.set_value(config_row.doctype, config_row.name, 'last_sync_status',
                    `Success - ${r.message.processed || 0} records processed`);

                frm.refresh_field('api_configurations');
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message ? r.message.error : __('Sync failed'),
                    indicator: 'red'
                });

                // Update sync status with error
                frappe.model.set_value(config_row.doctype, config_row.name, 'last_sync_status',
                    `Error: ${r.message ? r.message.error : 'Unknown error'}`);
                frm.refresh_field('api_configurations');
            }
        }
    });
}

function full_resync_device(frm, config_row) {
    if (!config_row.api_url || !config_row.api_key || !config_row.api_secret) {
        frappe.msgprint({
            title: __('Missing Information'),
            message: __('Please fill in API URL, API Key, and API Secret before syncing.'),
            indicator: 'orange'
        });
        return;
    }

    // Check if the document is saved
    if (!config_row.name || config_row.name.startsWith('new-')) {
        frappe.msgprint({
            title: __('Save Required'),
            message: __('Please save the document first before syncing.'),
            indicator: 'orange'
        });
        return;
    }

    // Confirm with user
    frappe.confirm(
        __('This will fetch the last 30 days of attendance data. Continue?'),
        function() {
            // Show progress indicator
            frappe.show_alert({
                message: __('Starting full resync (30 days) for {0}...', [config_row.configuration_name || config_row.api_url]),
                indicator: 'blue'
            });

            frappe.call({
                method: 'chundakadan.chundakadan.doctype.crosschex_settings.crosschex_settings.full_resync_device',
                args: {
                    api_url: config_row.api_url,
                    api_key: config_row.api_key,
                    config_row_name: config_row.name,
                    config_name: config_row.configuration_name
                },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint({
                            title: __('Success'),
                            message: r.message.message || __('Full resync completed!'),
                            indicator: 'green'
                        });

                        // Update sync status fields
                        frappe.model.set_value(config_row.doctype, config_row.name, 'last_sync_time', frappe.datetime.now_datetime());
                        frappe.model.set_value(config_row.doctype, config_row.name, 'last_sync_status',
                            `Success - ${r.message.processed || 0} records processed`);

                        frm.refresh_field('api_configurations');
                    } else {
                        frappe.msgprint({
                            title: __('Error'),
                            message: r.message ? r.message.error : __('Full resync failed'),
                            indicator: 'orange'
                        });

                        // Update sync status with error
                        frappe.model.set_value(config_row.doctype, config_row.name, 'last_sync_status',
                            `Error: ${r.message ? r.message.error : 'Unknown error'}`);
                        frm.refresh_field('api_configurations');
                    }
                }
            });
        }
    );
}
