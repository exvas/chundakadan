frappe.ui.form.on('Item', {
    custom_tax_template: function(frm) {
        if (frm.doc.custom_tax_template) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Tax Template',
                    name: frm.doc.custom_tax_template
                },
                callback: function(r) {
                    if (r.message) {
                        const item_tax_template = r.message.taxes;
                        
                        frm.clear_table('taxes');
                        
                        $.each(item_tax_template, function(index, row) {
                            let child = frm.add_child('taxes');
                            child.item_tax_template = row.item_tax_template; 
                            child.tax_category = row.tax_category;
                            child.valid_from = row.valid_from;
                            child.minimum_net_rate = row.minimum_net_rate;
                            child.maximum_net_rate = row.maximum_net_rate;
                        });
        
                        frm.refresh_field('taxes');
                    }
                }
            });
        } else {
            frm.clear_table('taxes');
            frm.refresh_field('taxes');
        }
    }
})