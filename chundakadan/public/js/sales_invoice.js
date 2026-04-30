if (!window.chundakadan_sales_invoice_loaded) {
  window.chundakadan_sales_invoice_loaded = true;

  const check_overdue_restriction = frappe.utils.debounce((frm) => {
    if (!frm.doc.customer) return;

    // Reset restriction bypass on customer change
    frm.doc.custom_ignore_overdue_restriction = 0;

    frappe.call({
      method: "chundakadan.doc_events.sales_invoice.check_overdue_unpaid_invoices",
      args: {
        customer: frm.doc.customer,
        posting_date: frm.doc.posting_date
      },
      callback: function(r) {
        if (r.message && r.message.length > 0) {
          // Check if a similar dialog is already open to prevent duplicates
          if ($('.modal-title:contains("Overdue Invoices Found")').length > 0) return;

          let invoice_list = r.message.map(d => `<li>${d.name} (Due: ${d.due_date})</li>`).join("");
          
          frappe.warn(
            __('Overdue Invoices Found'),
            __(`Customer <b>${frm.doc.customer}</b> has overdue unpaid invoices based on their payment schedule:<br><br><ul>${invoice_list}</ul><br>Creating new Sales Invoices for this customer is restricted. Do you want to continue?`),
            () => {
              // On Continue
              frm.doc.custom_ignore_overdue_restriction = 1;
              frappe.show_alert({
                message: __('Restriction bypassed for this document'),
                indicator: 'orange'
              });
            },
            __('Continue'),
            true // show_cancel button
          );
        }
      }
    });
  }, 500);

  frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
      chundakadan.utils.setup_item_selection(frm, 'items');
      toggle_ui(frm);

      if (frm.is_new()) {
        // Force posting date and time to be editable for new invoices
        frm.set_df_property('posting_date', 'read_only', 0);
        frm.set_df_property('posting_time', 'read_only', 0);

        if (frm.doc.customer) {
          check_overdue_restriction(frm);
        }
      }

      if (frm.fields_dict.items && frm.fields_dict.items.grid) {
        const item_code_field = frm.fields_dict.items.grid.get_field('item_code');
        if (item_code_field && item_code_field.$input) {
          item_code_field.$input.css({
            'cursor': 'pointer',
            'background-color': '#f8f9fa'
          });
        }
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
      if (frm.is_new()) {
        // Use direct doc assignment to avoid triggering change events during load
        frm.doc.set_posting_time = 1;
        
        // Default posting date to today even if pulled from other docs
        if (!frm.doc.posting_date || frm.doc.posting_date !== frappe.datetime.get_today()) {
          frm.set_value('posting_date', frappe.datetime.get_today());
        }
      }
      toggle_ui(frm);
    },

    posting_date: function(frm) {
      if (frm.doc.customer && frm.doc.posting_date) {
        check_overdue_restriction(frm);
      }
    },

    customer: function(frm) {
      if (frm.doc.customer) {
        check_overdue_restriction(frm);
      }
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
  });
}

function toggle_ui(frm) {
  if (!frm || !frm.doc) return;
  
  const isReturn = !!frm.doc.is_return;

  if (frm.toggle_display) {
    frm.toggle_display('workflow_state', isReturn);
  }

  if (isReturn) {
    if (!frm.is_new() && frm.doc.workflow_state) {
      if (frappe.workflow && frappe.workflow.setup) {
        frappe.workflow.setup(frm);
      }
      if (frm.page && frm.page.set_indicator) {
        frm.page.clear_indicator();
        frm.page.set_indicator(__(frm.doc.workflow_state), "blue");
      }
    }
  } else {
    if (frm.fields_dict && frm.fields_dict.workflow_state && frm.fields_dict.workflow_state.$wrapper) {
      frm.fields_dict.workflow_state.$wrapper.hide();
    }

    if (!frm.is_new() && frm.page) {
      if (frm.page.clear_actions_menu) {
        frm.page.clear_actions_menu();
      }

      if (frm.doc.docstatus === 0 && frm.perm && frm.perm[0] && frm.perm[0].submit) {
        frm.page.set_primary_action(__('Submit'), () => frm.savesubmit());
      }

      if (frm.page.set_indicator) {
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