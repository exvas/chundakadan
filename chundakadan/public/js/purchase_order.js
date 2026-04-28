frappe.ui.form.on('Purchase Order', {
    refresh: function(frm) {
        chundakadan.utils.setup_item_selection(frm, 'items', true);
    }
});
