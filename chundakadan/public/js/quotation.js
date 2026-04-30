frappe.ui.form.on('Quotation', {
    refresh: function(frm) {
        chundakadan.utils.setup_item_selection(frm, 'items');
    }
});
