frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
      toggle_ui(frm);
    },
    is_return(frm) {
      toggle_ui(frm);
    },
    onload(frm) {
        toggle_ui(frm);
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
  