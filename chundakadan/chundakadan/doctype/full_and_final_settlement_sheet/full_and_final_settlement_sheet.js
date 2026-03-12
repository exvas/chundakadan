frappe.ui.form.on("Full and Final Settlement Sheet", {
    refresh: function(frm) {
        if (!frm.doc.employee_details || frm.doc.employee_details.length === 0) {
            const employee_rows = [
                "Employee Name",
                "Employee ID",
                "Department",
                "Designation",
                "Date of Joining",
                "Last Working Day",
                "Total Service Period"
            ];

            employee_rows.forEach(label_name => {
                let row = frm.add_child("employee_details");
                frappe.model.set_value(row.doctype, row.name, "details", label_name);
            });

            frm.refresh_field("employee_details");
        }

        if (!frm.doc.earnings_breakdown || frm.doc.earnings_breakdown.length === 0) {
            const earnings_rows = [
                { properties: "Last Month Salary", description: "Basic + Allowances for [Month/Year]" },
                { properties: "Pending Salaries", description: "Unpaid wages from previous months" },
                { properties: "Overtime Pay", description: "As per company policy (if applicable)" },
                { properties: "Bonus/Commission", description: "Prorated incentive or performance bonus" },
                { properties: "Leave Encashment", description: "Unused paid leaves \u00d7 daily rate (max 30 days)" }, // \u00d7 is multiplication sign
                { properties: "Gratuity", description: "(Last drawn salary \u00d7 15/26) \u00d7 Service Years" },
                { properties: "Other Benefits", description: "Reimbursement, PF withdrawal interest" },
                { properties: "Total Earnings", description: "Sum of above" }
            ];

            earnings_rows.forEach(item => {
                let row = frm.add_child("earnings_breakdown");
                frappe.model.set_value(row.doctype, row.name, "properties", item.properties);
                frappe.model.set_value(row.doctype, row.name, "description", item.description);
            });

            frm.refresh_field("earnings_breakdown");
        }

        if (!frm.doc.deduction || frm.doc.deduction.length === 0) {
            const deduction_rows = [
                { component: "Advance Salary/Loans", descriptionformula: "Outstanding loans or salary advances" },
                { component: "Tax Deductions (TDS)", descriptionformula: "Income tax on final payout" },
                { component: "PF Contribution (Employer Share)", descriptionformula: "If not transferred" },
                { component: "ESI (if applicable)", descriptionformula: "Employee State Insurance" },
                { component: "Professional Tax", descriptionformula: "Pending PT dues" },
                { component: "Other Deductions", descriptionformula: "Equipment damage, notice period waiver" },
                { component: "Total Deductions", descriptionformula: "Sum of above" }
            ];

            deduction_rows.forEach(item => {
                let row = frm.add_child("deduction");
                frappe.model.set_value(row.doctype, row.name, "component", item.component);
                frappe.model.set_value(row.doctype, row.name, "descriptionformula", item.descriptionformula);
            });

            frm.refresh_field("deduction");
        }

        if (!frm.doc.net_settlement_amount || frm.doc.net_settlement_amount.length === 0) {
            const net_rows = [
                "Total Earnings",
                "Less: Total Deductions",
                "Net Payable"
            ];

            net_rows.forEach(entry_name => {
                let row = frm.add_child("net_settlement_amount");
                frappe.model.set_value(row.doctype, row.name, "entries", entry_name);
            });

            frm.refresh_field("net_settlement_amount");
        }

        if (!frm.doc.hr_approval || frm.doc.hr_approval.length === 0) {
            const hr_rows = [
                "Prepared By (HR Executive)",
                "Approved By (Manager)",
                "Authorized Signatory"
            ];

            hr_rows.forEach(role_name => {
                let row = frm.add_child("hr_approval");
                frappe.model.set_value(row.doctype, row.name, "role", role_name);
            });

            frm.refresh_field("hr_approval");
        }
    }
});
