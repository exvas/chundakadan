frappe.ui.form.on('Sales Invoice', {
  refresh(frm) {
  	if(!cur_frm.is_new()){
		  toggle_ui(frm);
	}
      if( frm.fields_dict.items.grid.get_field('item_code').$input){
      	frm.fields_dict.items.grid.get_field('item_code').$input.css({
			  'cursor': 'pointer',
			  'background-color': '#f8f9fa'
		  });
	  }


      // Add sync button for Sales Person
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
  is_return(frm) {
      toggle_ui(frm);
  },
  onload(frm) {
      toggle_ui(frm);
  },

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

  before_save: function(frm) {
      if (frm.doc.custom_sales_person && frm.doc.sales_team) {
          frm.doc.sales_team.forEach(function(row) {
              if (!row.sales_person || row.sales_person !== frm.doc.custom_sales_person) {
                  frappe.model.set_value(row.doctype, row.name, 'sales_person', frm.doc.custom_sales_person);
                  frappe.model.set_value(row.doctype, row.name, 'allocated_percentage', 100);
              }
          });
      }
  },
	customer: function () {
		if(cur_frm.doc.customer){
			frappe.call({
				method: "chundakadan.doc_events.sales_invoice.check_customer_overdue_transactions",
				args: {
					customer: cur_frm.doc.customer
				},
				freeze: true,
				freeze_message: "Checking Customer Overdue Transactions",
				callback: function () {

				}
			})
		}
	}

});

function toggle_ui(frm) {
  const isReturn = !!frm.doc.is_return;

  frm.toggle_display('workflow_state', isReturn);

  if (isReturn) {
      if (!frm.is_new() && frm.doc.workflow_state) {
          frappe.workflow.setup(frm);
          if (frm.page && frm.page.set_indicator) {
              frm.page.clear_indicator();
              frm.page.set_indicator(__(frm.doc.workflow_state), "blue");
          }
      }
  } else {
      frm.page.clear_actions_menu();

      if (frm.doc.docstatus === 0 && frm.perm[0]?.submit) {
          frm.page.set_primary_action(__('Submit'), () => frm.savesubmit());
      }
      if (frm.fields_dict.workflow_state) {
          frm.fields_dict.workflow_state.$wrapper.hide();
      }
      if (frm.page && frm.page.set_indicator) {
          frm.page.clear_indicator();
          if (frm.doc.status) {
              let color = "blue";
              if (frm.doc.status === "Draft") color = "orange";
              else if (frm.doc.status === "Submitted") color = "green";
              else if (frm.doc.status === "Paid") color = "green";
              else if (frm.doc.status === "Unpaid") color = "red";
              else if (frm.doc.status === "Overdue") color = "red";
              else if (frm.doc.status === "Cancelled") color = "grey";

              frm.page.set_indicator(__(frm.doc.status), color);
          }
      }
  }
}

frappe.ui.form.on('Sales Invoice Item', {
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
      primary_action_label: __('Close'),
      primary_action: function() {
          dialog.hide();
      }
  });

  dialog.show();
}

function search_filtered_items(dialog, frm, cdt, cdn) {
  let item_group = dialog.get_value('item_group');
  let brand = dialog.get_value('brand');
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

  if (brand) {
      filters['custom_finish'] = brand;
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

// Sales Team child table event handler
frappe.ui.form.on('Sales Team', {
    sales_team_add: function(frm, cdt, cdn) {
        if (frm.doc.custom_sales_person) {
            frappe.model.set_value(cdt, cdn, 'sales_person', frm.doc.custom_sales_person);
            frappe.model.set_value(cdt, cdn, 'allocated_percentage', 100);
        }
    }
});