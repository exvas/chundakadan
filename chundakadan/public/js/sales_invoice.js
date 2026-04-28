frappe.ui.form.on('Sales Invoice', {
  refresh(frm) {
  	if(!cur_frm.is_new()){
		  toggle_ui(frm);
	}
      chundakadan.utils.setup_item_selection(frm, 'items');


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
	customer: function (frm) {
		if(frm.doc.customer){
			frappe.call({
				method: "chundakadan.doc_events.sales_invoice.check_overdue_unpaid_invoices",
				args: {
					customer: frm.doc.customer
				},
				freeze: true,
				freeze_message: "Checking Customer Overdue Transactions",
				callback: function (r) {
                    if (r.message && r.message.length > 0) {
                        frappe.msgprint({
                            title: __('Overdue Unpaid Invoices'),
                            indicator: 'orange',
                            message: __('Customer has unpaid invoices older than their credit days. Please review before proceeding.')
                        });
                    }
				}
			})
		}
	},
    validate: function(frm) {
        if (frm.doc.__confirmed_overdue) {
            return;
        }

        if (frm.doc.customer && !frm.doc.is_return && frm.doc.docstatus === 0) {
            frappe.validated = false;
            frappe.call({
                method: "chundakadan.doc_events.sales_invoice.check_overdue_unpaid_invoices",
                args: {
                    customer: frm.doc.customer
                },
                callback: function (r) {
                    if (r.message && r.message.length > 0) {
                        let invoice_names = r.message.map(i => i.name).join(', ');
                        let msg = __("Customer has unpaid invoices ({0}) older than their credit days. Do you want to continue?", [invoice_names]);
                        
                        frappe.confirm(msg, 
                            function() {
                                frm.doc.__confirmed_overdue = true;
                                frm.save();
                            },
                            function() {
                                frappe.validated = false;
                            }
                        );
                    } else {
                        frappe.validated = true;
                        frm.doc.__confirmed_overdue = true; // Set to true to avoid re-checking in this cycle
                        frm.save();
                    }
                }
            });
        }
    },

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


// Sales Team child table event handler
frappe.ui.form.on('Sales Team', {
    sales_team_add: function(frm, cdt, cdn) {
        if (frm.doc.custom_sales_person) {
            frappe.model.set_value(cdt, cdn, 'sales_person', frm.doc.custom_sales_person);
            frappe.model.set_value(cdt, cdn, 'allocated_percentage', 100);
        }
    }
});
