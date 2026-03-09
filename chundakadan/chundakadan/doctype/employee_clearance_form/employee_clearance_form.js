frappe.ui.form.on("Employee Clearance Form", {
    employee_name: function(frm) {
        if (frm.doc.employee_name) {
            frappe.db.get_value('Employee', frm.doc.employee_name, ['designation', 'department'], (r) => {
                if (r) {
                    frm.set_value('designation', r.designation);
                    frm.set_value('department', r.department);
                }
            });
        } else {
            frm.set_value('designation', "");
            frm.set_value('department', "");
        }
    }
});
