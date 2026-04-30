frappe.ui.form.on('Purchase Invoice', {
    refresh: function(frm) {
        chundakadan.utils.setup_item_selection(frm, 'items', true);
    }
});
