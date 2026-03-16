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
                { properties: "Leave Encashment", description: "Unused paid leaves × daily rate (max 30 days)" },
                { properties: "Gratuity", description: "(Last drawn salary × 15/26) × Service Years" },
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

        if (!frm.doc.custom_employee) {
            // Clear Employee Details data
            (frm.doc.employee_details || []).forEach(row => {
                frappe.model.set_value(row.doctype, row.name, "data", "");
            });

            // Clear Earnings Breakdown remarks and reset descriptions
            (frm.doc.earnings_breakdown || []).forEach(row => {
                frappe.model.set_value(row.doctype, row.name, "remarks", "");
                if (row.properties === "Last Month Salary") {
                    frappe.model.set_value(row.doctype, row.name, "description", "Basic + Allowances for [Month/Year]");
                }
                if (row.properties === "Leave Encashment") {
                    frappe.model.set_value(row.doctype, row.name, "description", "Unused paid leaves × daily rate (max 30 days)");
                }
            });

            // Clear Deduction amounts
            (frm.doc.deduction || []).forEach(row => {
                frappe.model.set_value(row.doctype, row.name, "amount", "");
            });

            frm.refresh_field("employee_details");
            frm.refresh_field("earnings_breakdown");
            frm.refresh_field("deduction");
            return;
        }

        let emp = await frappe.db.get_doc("Employee", frm.doc.custom_employee);

        /* -- Reset all auto-fetched fields before populating new employee data -- */
        (frm.doc.employee_details || []).forEach(row => {
            frappe.model.set_value(row.doctype, row.name, "data", "");
        });
        (frm.doc.earnings_breakdown || []).forEach(row => {
            frappe.model.set_value(row.doctype, row.name, "remarks", "");
            if (row.properties === "Last Month Salary")
                frappe.model.set_value(row.doctype, row.name, "description", "Basic + Allowances for [Month/Year]");
            if (row.properties === "Leave Encashment")
                frappe.model.set_value(row.doctype, row.name, "description", "Unused paid leaves × daily rate (max 30 days)");
        });
        (frm.doc.deduction || []).forEach(row => {
            frappe.model.set_value(row.doctype, row.name, "amount", "");
        });
        frm.refresh_field("employee_details");
        frm.refresh_field("earnings_breakdown");
        frm.refresh_field("deduction");

        /* ---------------- EMPLOYEE DETAILS ---------------- */

        frm.doc.employee_details.forEach(row => {

            if (row.details === "Employee Name")
                frappe.model.set_value(row.doctype, row.name, "data", emp.employee_name);

            if (row.details === "Employee ID")
                frappe.model.set_value(row.doctype, row.name, "data", emp.name);

            if (row.details === "Department")
                frappe.model.set_value(row.doctype, row.name, "data", emp.department);

            if (row.details === "Designation")
                frappe.model.set_value(row.doctype, row.name, "data", emp.designation);

            if (row.details === "Date of Joining")
                frappe.model.set_value(row.doctype, row.name, "data", emp.date_of_joining);

            if (row.details === "Last Working Day")
                frappe.model.set_value(row.doctype, row.name, "data", emp.relieving_date || "");


            if (row.details === "Total Service Period") {

                if (emp.date_of_joining) {

                    let start = frappe.datetime.str_to_obj(emp.date_of_joining);

                    let end = emp.relieving_date
                        ? frappe.datetime.str_to_obj(emp.relieving_date)
                        : new Date();

                    let diff = frappe.datetime.get_day_diff(end, start);

                    let years = Math.floor(diff / 365);
                    let months = Math.floor((diff % 365) / 30);

                    frappe.model.set_value(
                        row.doctype,
                        row.name,
                        "data",
                        years + " Years " + months + " Months"
                    );
                }
            }

        });

        frm.refresh_field("employee_details");


        /* ---------------- LAST MONTH SALARY ---------------- */

        // Relieving date is YYYY-MM-DD (from Employee doc)
        let relieving = emp.relieving_date || frappe.datetime.get_today();

        // Calculate the target month = month BEFORE the relieving month
        let rDate = new Date(relieving); // works because it is YYYY-MM-DD
        let targetMonth = rDate.getMonth() === 0 ? 11 : rDate.getMonth() - 1; // 0-indexed
        let targetYear  = rDate.getMonth() === 0 ? rDate.getFullYear() - 1 : rDate.getFullYear();

        // Helper: parse both YYYY-MM-DD and DD-MM-YYYY safely
        const parseDate = (s) => {
            if (!s) return null;
            let p = String(s).split("-");
            if (p.length !== 3) return null;
            if (p[0].length === 4) return new Date(+p[0], +p[1] - 1, +p[2]); // YYYY-MM-DD
            return new Date(+p[2], +p[1] - 1, +p[0]);                        // DD-MM-YYYY
        };

        // Fetch ALL submitted slips for this employee (limit 0 = unlimited, needed for EPF/ESI totals)
        let allSlips = await frappe.db.get_list("Salary Slip", {
            filters: [
                ["employee", "=", emp.name],
                ["docstatus", "=", 1]
            ],
            fields: ["name", "net_pay", "start_date", "end_date"],
            limit: 0
        });

        // Find the slip whose end_date falls in the target month/year (PREVIOUS month = Last Month Salary)
        let slip = allSlips.find(s => {
            let ed = parseDate(s.end_date);
            return ed && ed.getMonth() === targetMonth && ed.getFullYear() === targetYear;
        });

        if (slip) {
            let ed = parseDate(slip.end_date);
            let month_names = ["January","February","March","April","May","June",
                               "July","August","September","October","November","December"];
            let month_name = month_names[ed.getMonth()];
            let year = ed.getFullYear();

            frm.doc.earnings_breakdown.forEach(row => {
                if (row.properties === "Last Month Salary") {
                    frappe.model.set_value(row.doctype, row.name, "remarks", slip.net_pay);
                    frappe.model.set_value(row.doctype, row.name, "description",
                        `Basic + Allowances for ${month_name} ${year}`);
                }
            });

            frm.refresh_field("earnings_breakdown");
        }

        /* -------- ADVANCE RECOVERY (from relieving month slip) -------- */
        // Find the salary slip whose start_date and end_date are in the SAME month as relieving date
        let relievingMonth = rDate.getMonth();   // 0-indexed
        let relievingYear  = rDate.getFullYear();

        let relievingSlip = allSlips.find(s => {
            let sd = parseDate(s.start_date);
            let ed = parseDate(s.end_date);
            return sd && ed
                && sd.getMonth() === relievingMonth && sd.getFullYear() === relievingYear
                && ed.getMonth() === relievingMonth && ed.getFullYear() === relievingYear;
        });

        let advance_recovery = 0;

        if (relievingSlip) {
            let slip_doc = await frappe.db.get_doc("Salary Slip", relievingSlip.name);
            if (slip_doc && slip_doc.deductions) {
                slip_doc.deductions.forEach(d => {
                    if (d.salary_component === "Employee Advance Recovery")
                        advance_recovery = d.amount;
                });
            }
        }

        frm.doc.deduction.forEach(row => {
            if (row.component === "Advance Salary/Loans")
                frappe.model.set_value(row.doctype, row.name, "amount", advance_recovery || "");
        });

        frm.refresh_field("deduction");



        /* ---------------- PENDING SALARIES (draft slip of relieving month) ---------------- */

        // Fetch draft salary slips (docstatus = 0) for this employee
        let draftSlips = await frappe.db.get_list("Salary Slip", {
            filters: [
                ["employee", "=", emp.name],
                ["docstatus", "=", 0]
            ],
            fields: ["name", "net_pay", "start_date", "end_date"],
            limit: 50
        });

        // Find the draft slip whose start_date and end_date are in the SAME month as relieving date
        let pendingSlip = draftSlips.find(s => {
            let sd = parseDate(s.start_date);
            let ed = parseDate(s.end_date);
            return sd && ed
                && sd.getMonth() === relievingMonth && sd.getFullYear() === relievingYear
                && ed.getMonth() === relievingMonth && ed.getFullYear() === relievingYear;
        });

        frm.doc.earnings_breakdown.forEach(row => {
            if (row.properties === "Pending Salaries") {
                frappe.model.set_value(row.doctype, row.name, "remarks",
                    pendingSlip ? pendingSlip.net_pay : "");
            }
        });

        frm.refresh_field("earnings_breakdown");
        /* -------- EPF & ESI TOTALS (Theoretical calculation based on Formula + Months) -------- */
        
        let totalEPF = 0;
        let totalESI = 0;

        // 1. Calculate Total Months
        let joiningDate = emp.date_of_joining ? frappe.datetime.str_to_obj(emp.date_of_joining) : null;
        let rDateObj = emp.relieving_date ? frappe.datetime.str_to_obj(emp.relieving_date) : new Date();

        if (joiningDate && rDateObj) {
            let dayDiff = frappe.datetime.get_day_diff(rDateObj, joiningDate);
            let totalMonthsInService = Math.round(dayDiff / 30); // Approximate months
            console.log("FF Sheet: Total months in service (approx):", totalMonthsInService);

            // 2. Fetch Salary Structure Assignment
            let assignment = await frappe.db.get_list("Salary Structure Assignment", {
                filters: { employee: emp.name, docstatus: 1 },
                fields: ["base", "salary_structure"],
                order_by: "from_date desc",
                limit_page_length: 1
            });

            if (assignment && assignment.length > 0) {
                let base_salary = flt(assignment[0].base);
                let structure_name = assignment[0].salary_structure;
                console.log(`FF Sheet: Found assignment. Base: ${base_salary}, Structure: ${structure_name}`);

                // 3. Fetch Salary Structure Details (Deductions table)
                let structure = await frappe.db.get_doc("Salary Structure", structure_name);
                
                if (structure && structure.deductions) {
                    structure.deductions.forEach(d => {
                        let formula = d.formula;
                        if (!formula) return;

                        // Helper to evaluate formula (handles Python-style if/else)
                        let getMonthlyAmount = (frmla, base) => {
                            try {
                                let f = frmla.toLowerCase().replace(/\bbase\b/g, base);
                                
                                // Transform Python "A if B else C" to JS "B ? A : C"
                                if (f.includes(" if ") && f.includes(" else ")) {
                                    f = f.replace(/(.*)\s+if\s+(.*)\s+else\s+(.*)/g, "($2) ? ($1) : ($3)");
                                }
                                
                                let result = new Function(`return ${f}`)();
                                return isNaN(result) ? 0 : flt(result);
                            } catch (e) {
                                console.error("FF Sheet: Formula evaluation failed:", frmla, e);
                                return 0;
                            }
                        };

                        if (d.salary_component === "ESI") {
                            let monthlyESI = getMonthlyAmount(formula, base_salary);
                            totalESI = flt(monthlyESI * totalMonthsInService);
                            console.log(`FF Sheet: ESI Monthly: ${monthlyESI}, Total: ${totalESI}`);
                        }

                        if (d.salary_component === "EPF") {
                            let monthlyEPF = getMonthlyAmount(formula, base_salary);
                            totalEPF = flt(monthlyEPF * totalMonthsInService);
                            console.log(`FF Sheet: EPF Monthly: ${monthlyEPF}, Total: ${totalEPF}`);
                        }
                    });
                }
            } else {
                console.log("FF Sheet: No submitted Salary Structure Assignment found.");
            }
        }

        frm.doc.deduction.forEach(row => {
            if (row.component === "PF Contribution (Employer Share)")
                frappe.model.set_value(row.doctype, row.name, "amount", totalEPF);
            if (row.component === "ESI (if applicable)")
                frappe.model.set_value(row.doctype, row.name, "amount", totalESI);
        });

        frm.refresh_field("deduction");

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


        if (report.message && report.message.result) {

            let total = 0;

            let payment_days = report.message.result[0].payment_days;

            let per_day_rate = report.message.result[0].per_day_rate;


            report.message.result.forEach(r => {

                total += r.total_payable_amount || 0;

            });


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