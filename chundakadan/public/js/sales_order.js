frappe.ui.form.on('Sales Order', {
    custom_sales_person: function(frm) {
        if (frm.doc.custom_sales_person) {
            if (!frm.doc.sales_team || frm.doc.sales_team.length === 0) {
                let row = frm.add_child('sales_team');
                row.sales_person = frm.doc.custom_sales_person;
                row.allocated_percentage = 100;
            } else {
                frm.doc.sales_team.forEach(function(row, index) {
                    frappe.model.set_value(row.doctype, row.name, 'sales_person', frm.doc.custom_sales_person);
                    frappe.model.set_value(row.doctype, row.name, 'allocated_percentage', 100);
                });
            }
            frm.refresh_field('sales_team');
        }
    },
    
    refresh: function(frm) {
        chundakadan.utils.setup_item_selection(frm, 'items');
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Sync Sales Person'), function() {
                if (frm.doc.custom_sales_person) {
                    if (!frm.doc.sales_team || frm.doc.sales_team.length === 0) {
                        let row = frm.add_child('sales_team');
                        row.sales_person = frm.doc.custom_sales_person;
                        row.allocated_percentage = 100;
                    } else {
                        frm.doc.sales_team.forEach(function(row) {
                            frappe.model.set_value(row.doctype, row.name, 'sales_person', frm.doc.custom_sales_person);
                            frappe.model.set_value(row.doctype, row.name, 'allocated_percentage', 100);
                        });
                    }
                    frm.refresh_field('sales_team');
                    frappe.show_alert(__('Sales person synced successfully'));
                } else {
                    frappe.show_alert(__('Please select a sales person first'));
                }
            });
        }
    },
    
    before_save: function(frm) {
        if (frm.doc.custom_sales_person && frm.doc.sales_team) {
            frm.doc.sales_team.forEach(function(row) {
                if (!row.sales_person || row.sales_person !== frm.doc.custom_sales_person) {
                    frappe.model.set_value(row.doctype, row.name, 'sales_person', frm.doc.custom_sales_person);
                    frappe.model.set_value(row.doctype, row.name, 'allocated_percentage', 100);
                }
            });
        }
    }
});

frappe.ui.form.on('Sales Team', {
    sales_team_add: function(frm, cdt, cdn) {
        if (frm.doc.custom_sales_person) {
            frappe.model.set_value(cdt, cdn, 'sales_person', frm.doc.custom_sales_person);
            frappe.model.set_value(cdt, cdn, 'allocated_percentage', 100);
            console.log('Set values for new row');
        }
    }
});