frappe.ui.form.on("Full and Final Settlement Sheet", {
    refresh: function (frm) {
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
    },
    custom_employee: async function (frm) {

        if (!frm.doc.custom_employee) return;

        // Get Employee
        let emp = await frappe.db.get_doc("Employee", frm.doc.custom_employee);

        /* ---------------- EMPLOYEE DETAILS TABLE ---------------- */

        frm.doc.employee_details.forEach(row => {

            if (row.details === "Employee Name") {
                frappe.model.set_value(row.doctype, row.name, "data", emp.employee_name);
            }

            if (row.details === "Employee ID") {
                frappe.model.set_value(row.doctype, row.name, "data", emp.name);
            }

            if (row.details === "Department") {
                frappe.model.set_value(row.doctype, row.name, "data", emp.department);
            }

            if (row.details === "Designation") {
                frappe.model.set_value(row.doctype, row.name, "data", emp.designation);
            }

            if (row.details === "Date of Joining") {
                frappe.model.set_value(row.doctype, row.name, "data", emp.date_of_joining);
            }

            if (row.details === "Last Working Day") {
                frappe.model.set_value(row.doctype, row.name, "data", emp.relieving_date || "");
            }

            if (row.details === "Total Service Period") {

                if (emp.date_of_joining) {

                    let start = frappe.datetime.str_to_obj(emp.date_of_joining);
                    let end = emp.relieving_date
                        ? frappe.datetime.str_to_obj(emp.relieving_date)
                        : new Date();

                    let diff = frappe.datetime.get_day_diff(end, start);

                    let years = Math.floor(diff / 365);
                    let months = Math.floor((diff % 365) / 30);

                    let service = years + " Years " + months + " Months";

                    frappe.model.set_value(row.doctype, row.name, "data", service);
                }
            }

        });

        frm.refresh_field("employee_details");


        /* ---------------- LAST MONTH SALARY FROM SALARY SLIP ---------------- */

        if (!emp.relieving_date) return;

        let date = frappe.datetime.str_to_obj(emp.relieving_date);
        let month = date.getMonth() + 1;
        let year = date.getFullYear();

        let salary_slips = await frappe.db.get_list("Salary Slip", {
            filters: {
                employee: emp.name,
                docstatus: 1
            },
            fields: ["name", "net_pay", "end_date"],
            limit: 12
        });

        // Fetch latest salary slip before relieving date
        let slips = await frappe.db.get_list("Salary Slip", {
            filters: [
                ["employee", "=", emp.name],
                ["end_date", "<=", emp.relieving_date],
                ["docstatus", "=", 1]
            ],
            fields: ["name", "net_pay", "end_date"],
            order_by: "end_date desc",
            limit: 1
        });

        if (slips.length > 0) {

            let slip = slips[0];

            frm.doc.earnings_breakdown.forEach(row => {

                if (row.properties === "Last Month Salary") {

                    frappe.model.set_value(
                        row.doctype,
                        row.name,
                        "remarks",
                        slip.net_pay
                    );

                }

            });
            frm.refresh_field("earnings_breakdown");
        }

        // Call Leave Encashment Monthly Balance report
        let report = await frappe.call({
            method: "frappe.desk.query_report.run",
            args: {
                report_name: "Leave Encashment Monthly Balance",
                filters: {
                    company: frm.doc.company,
                    employee: emp.name,
                    payment_days: 30
                }
            }
        });

        if (report.message && report.message.result && report.message.result.length > 0) {

            let total = 0;
            let payment_days = report.message.result[0].payment_days;
            let per_day_rate = report.message.result[0].per_day_rate;

            report.message.result.forEach(row => {
                total += row.total_payable_amount || 0;
            });

            // Removed Payment Days and Per Day Rate from employee_details table as requested
            
            frm.refresh_field("employee_details");

            frm.doc.earnings_breakdown.forEach(row => {

                if (row.properties === "Leave Encashment") {

                    frappe.model.set_value(
                        row.doctype,
                        row.name,
                        "remarks",
                        total
                    );

                    frappe.model.set_value(
                        row.doctype,
                        row.name,
                        "description",
                        `Leave Encashment (${per_day_rate} per day for ${payment_days} payment days)`
                    );

                }

            });

            frm.refresh_field("earnings_breakdown");
        }
    }


});
