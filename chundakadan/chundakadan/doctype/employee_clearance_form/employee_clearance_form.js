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
            frappe.db.get_value('Employee', frm.doc.employee_name, 
                ['employee_name', 'designation', 'department', 'relieving_date', 'reports_to'], 
                (r) => {
                    if (r) {
                        frm.set_value('id_no', r.employee_name);
                        frm.set_value('designation', r.designation);
                        frm.set_value('department', r.department);
                        frm.set_value('date_of_exit_transfer__rotation_effective_from', r.relieving_date);
                        
                        if (r.reports_to) {
                            frappe.db.get_value('Employee', r.reports_to, 'employee_name', (res) => {
                                if (res) {
                                    frm.set_value('name_of_reporting_officer', res.employee_name);
                                }
                            });
                        } else {
                            frm.set_value('name_of_reporting_officer', "");
                        }
                    }
                }
            );
        } else {
            frm.set_value('id_no', "");
            frm.set_value('designation', "");
            frm.set_value('department', "");
            frm.set_value('date_of_exit_transfer__rotation_effective_from', "");
            frm.set_value('name_of_reporting_officer', "");
        }
    }
});
