frappe.ui.form.on('Payment Entry', {
    before_save: function(frm) {
        const ref = (frm.doc.references || []).find(r => r.reference_doctype && r.reference_name);

        if (ref) {
            return frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: ref.reference_doctype,
                    name: ref.reference_name
                },
                callback: function(response) {
                    if (response.message && response.message.custom_sales_person) {
                        frm.set_value('custom_sales_person', response.message.custom_sales_person);
                    }
                }
            });
        }
    }
});
