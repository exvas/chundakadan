// Copyright (c) 2026, Ashkar and contributors
// "Fetch Late Arrival Deduction" — pull this employee's late check-ins for the
// payroll month into the Late Entry Details table and set Amount = total.

frappe.ui.form.on("Additional Salary", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0) return; // only editable drafts

		frm.add_custom_button(__("Fetch Late Arrival Deduction"), function () {
			if (!frm.doc.employee) {
				frappe.msgprint(__("Select an Employee first."));
				return;
			}
			if (!frm.doc.payroll_date) {
				frappe.msgprint(__("Set the Payroll Date first — the whole month around it is used."));
				return;
			}
			frappe.call({
				method: "chundakadan.chundakadan.report.late_entry_deduction.late_entry_deduction.get_late_entries_for_month",
				args: { employee: frm.doc.employee, payroll_date: frm.doc.payroll_date },
				freeze: true,
				freeze_message: __("Fetching late check-ins..."),
				callback: function (r) {
					const d = r.message;
					if (!d) return;
					if (!d.rows || !d.rows.length) {
						frappe.msgprint(
							__("No late check-ins found for {0} between {1} and {2}.", [
								frm.doc.employee_name || frm.doc.employee,
								d.from_date,
								d.to_date,
							])
						);
						return;
					}
					frm.set_value("salary_component", "Late Arrival Deduction");
					frm.clear_table("custom_late_entry_details");
					d.rows.forEach(function (row) {
						const c = frm.add_child("custom_late_entry_details");
						c.attendance_date = row.date;
						c.check_in_time = row.check_in;
						c.shift = row.shift;
						c.late_minutes = row.late_minutes;
						c.deduction = row.deduction;
					});
					frm.refresh_field("custom_late_entry_details");
					frm.set_value("amount", d.total);
					frm.set_value(
						"custom_reason",
						__("Late entry deduction {0} to {1}: {2} late min over {3} day(s)", [
							d.from_date,
							d.to_date,
							d.total_minutes,
							d.late_days,
						])
					);
					frappe.show_alert(
						{
							message: __("{0} late day(s), {1} min → {2}", [
								d.late_days,
								d.total_minutes,
								format_currency(d.total),
							]),
							indicator: "orange",
						},
						7
					);
				},
			});
		});
	},
});
