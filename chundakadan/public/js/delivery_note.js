frappe.ui.form.on('Delivery Note', {
    refresh: function(frm) {
        chundakadan.utils.setup_item_selection(frm, 'items');
    }
});
