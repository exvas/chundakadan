frappe.ui.form.on('Quotation', {
    refresh: function(frm) {
        if (frm.fields_dict.items.grid.get_field('item_code').$input) {
            frm.fields_dict.items.grid.get_field('item_code').$input.css({
                'cursor': 'pointer',
                'background-color': '#f8f9fa'
            });
        }
    }
});

frappe.ui.form.on('Quotation Item', {
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
  
        if (row.item_code && !row._from_dialog) {
            frappe.model.set_value(cdt, cdn, 'item_code', '');
            show_item_selection_dialog(frm, cdt, cdn);
        } else if (row._from_dialog) {
            delete row._from_dialog;
        }
    }
});
  
function show_item_selection_dialog(frm, cdt, cdn) {
    let dialog = new frappe.ui.Dialog({
        title: __('Select Item'),
        fields: [
            {
                fieldname: 'item_group',
                fieldtype: 'Link',
                label: __('Item Group'),
                options: 'Item Group',
                reqd: 1
            },
            {
                fieldname: 'size',
                fieldtype: 'Link',
                label: __('Model & Size'),
                options: 'Size',
                get_query: function () {
                      const item_group = dialog.get_value("item_group")
                      return {
                          filters: {
                              item_group: item_group
                          }
                      };
                  }
            },
            {
              fieldname: 'finish',
              fieldtype: 'Link',
              label: __('Finish'),
              options: 'Finish Item',
                get_query: function () {
                      const item_group = dialog.get_value("item_group")
                      return {
                          filters: {
                              item_group: item_group
                          }
                      };
                  }
          },
            {
                fieldname: 'search_button',
                fieldtype: 'Button',
                label: __('Search Items'),
                click: function() {
                    search_filtered_items(dialog, frm, cdt, cdn);
                }
            },
            {
                fieldname: 'section_break',
                fieldtype: 'Section Break'
            },
            {
                fieldname: 'items_html',
                fieldtype: 'HTML',
                label: __('Available Items')
            }
        ],
        primary_action_label: __('OK'),
        primary_action: function() {
            let item_group = dialog.get_value('item_group');
            let size = dialog.get_value('size');
            let finish = dialog.get_value('finish');

            if (!item_group) {
                frappe.msgprint(__('Please select an Item Group'));
                return;
            }

            let filters = {
                'item_group': item_group,
                'custom_size': size || '',
                'custom_finish': finish || '',
                'disabled': 0,
                'is_sales_item': 1
            };

            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item',
                    filters: filters,
                    fieldname: 'name'
                },
                callback: function(r) {
                    if (r.message && r.message.name) {
                        select_item_from_dialog(r.message.name, cdt, cdn);
                        dialog.hide();
                    } else {
                        frappe.msgprint(__('No item found matching the selected criteria.'));
                    }
                }
            });
        },
        secondary_action_label: __('Close'),
        secondary_action: function() {
            dialog.hide();
        }
    });
  
    dialog.show();
}
  
function search_filtered_items(dialog, frm, cdt, cdn) {
    let item_group = dialog.get_value('item_group');
    let finish = dialog.get_value('finish');
    let size = dialog.get_value('size');
  
    if (!item_group) {
        frappe.msgprint(__('Please select an Item Group'));
        return;
    }
  
    let filters = {
        'item_group': item_group,
        'disabled': 0,
        'is_sales_item': 1
    };
  
    if (finish) {
        filters['custom_finish'] = finish;
    }
  
    if (size) {
        filters['custom_size'] = size;
    }
  
    dialog.fields_dict.items_html.$wrapper.html(`
        <div class="text-center" style="padding: 20px;">
            <i class="fa fa-spinner fa-spin"></i> Loading items...
        </div>
    `);
  
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Item',
            filters: filters,
            fields: ['name', 'item_name', 'item_group', 'brand', 'custom_size', 'stock_uom', 'image', 'custom_finish'],
            limit_page_length: 50,
            order_by: 'item_name'
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                display_items_grid(dialog, r.message, frm, cdt, cdn);
            } else {
                dialog.fields_dict.items_html.$wrapper.html(`
                    <div class="alert alert-info">
                        <i class="fa fa-info-circle"></i> No items found with the selected criteria.
                    </div>
                `);
            }
        }
    });
}
  
function display_items_grid(dialog, items, frm, cdt, cdn) {
    let html = `
        <div class="item-selection-grid">
            <style>
                .item-selection-grid {
                    max-height: 400px;
                    overflow-y: auto;
                    border: 1px solid #d1d8dd;
                    border-radius: 4px;
                }
                .item-card {
                    border-bottom: 1px solid #f0f0f0;
                    padding: 15px;
                    cursor: pointer;
                    transition: background-color 0.2s;
                }
                .item-card:hover {
                    background-color: #f8f9fa;
                }
                .item-card:last-child {
                    border-bottom: none;
                }
                .item-image {
                    width: 50px;
                    height: 50px;
                    object-fit: cover;
                    border-radius: 4px;
                    margin-right: 15px;
                }
                .item-details {
                    flex: 1;
                }
                .item-name {
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 5px;
                }
                .item-code {
                    color: #6c757d;
                    font-size: 12px;
                    margin-bottom: 5px;
                }
                .item-meta {
                    font-size: 12px;
                    color: #6c757d;
                }
                .item-rate {
                    color: #28a745;
                    font-weight: bold;
                }
            </style>
    `;
  
    items.forEach(item => {
        let image_html = '';
        if (item.image) {
            image_html = `<img src="${item.image}" class="item-image" alt="${item.item_name}">`;
        } else {
            image_html = `<div class="item-image" style="background-color: #e9ecef; display: flex; align-items: center; justify-content: center; color: #6c757d;"><i class="fa fa-image"></i></div>`;
        }
  
        html += `
            <div class="item-card" onclick="select_item_from_dialog('${item.name}', '${cdt}', '${cdn}')">
                <div style="display: flex; align-items: center;">
                    ${image_html}
                    <div class="item-details">
                        <div class="item-name">${item.item_name}</div>
                        <div class="item-code">${item.name}</div>
                        <div class="item-meta">
                            Group: ${item.item_group} | 
                            Brand: ${item.brand || 'N/A'} | 
                            Size: ${item.custom_size || 'N/A'}
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
  
    html += '</div>';
    dialog.fields_dict.items_html.$wrapper.html(html);
}
  
window.select_item_from_dialog = function(item_code, cdt, cdn) {
    let row = locals[cdt][cdn];
  
    row._from_dialog = true;
  
    frappe.model.set_value(cdt, cdn, 'item_code', item_code).then(() => {
        let grid_row = cur_frm.fields_dict.items.grid.grid_rows_by_docname[cdn];
        if (grid_row) {
            grid_row.on_grid_fields_dict.item_code.df.onchange &&
            grid_row.on_grid_fields_dict.item_code.df.onchange();
  
            grid_row.refresh();
        }
  
        if (cur_dialog) {
            cur_dialog.hide();
        }
  
        frappe.show_alert({
            message: __('Item selected successfully'),
            indicator: 'green'
        }, 3);
    });
};
