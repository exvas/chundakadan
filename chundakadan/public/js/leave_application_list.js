frappe.listview_settings['Leave Application'] = {

    onload: function (listview) {

        // Override setup_columns to remove the default Status column
        const original_setup_columns = listview.setup_columns.bind(listview);
        listview.setup_columns = function () {
            original_setup_columns();
            listview.columns = listview.columns.filter(
                (col) => col.type !== 'Status'
            );
        };

        // Re-run so the current render picks up the change
        listview.setup_columns();
        listview.render_header(true);

    }

};