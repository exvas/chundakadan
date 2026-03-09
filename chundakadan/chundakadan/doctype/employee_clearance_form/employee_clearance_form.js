frappe.ui.form.on("Employee Clearance Form", {
    onload: function(frm) {
        if (frm.is_new() && (!frm.doc.department_approval || frm.doc.department_approval.length === 0)) {
            const static_rows = [
                "Reporting officer",
                "Accounts /Finance",
                "HRD"
            ];
            
            static_rows.forEach(row_name => {
                let row = frm.add_child("department_approval");
                row.department_approval = row_name;
            });
            
            frm.refresh_field("department_approval");
        }

        if (frm.is_new() && (!frm.doc.table_vmjo || frm.doc.table_vmjo.length === 0)) {
            const mgmt_rows = [
                "GM",
                "MD"
            ];
            
            mgmt_rows.forEach(row_name => {
                let row = frm.add_child("table_vmjo");
                row.approved_by = row_name;
            });
            
            frm.refresh_field("table_vmjo");
        }
    },
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
