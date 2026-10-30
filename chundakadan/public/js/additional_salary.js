// Copyright (c) 2026, Ashkar and contributors
// "Fetch Late Arrival Deduction" — pull this employee's late check-ins for the
// payroll month into the Late Entry Details table and set Amount = total.
//
// A fetched day can be dropped: a late arrival that was approved should not be
// cut. Removing the row re-adds nothing, it only takes that day's deduction out
// of Amount and out of the sentence in Reason, so the figure always matches the
// days still listed. Rows cannot be added or edited by hand — the columns are
// read-only and the grid refuses new rows — so the only honest edit is removal.

const LATE_TABLE = "custom_late_entry_details";

// Amount and Reason follow whatever days are left in the table.
function chundakadan_sync_late_total(frm) {
	const rows = frm.doc[LATE_TABLE] || [];
	let total = 0;
	let minutes = 0;
	rows.forEach(function (r) {
		total += flt(r.deduction);
		minutes += cint(r.late_minutes);
	});
	frm.set_value("amount", Math.round(total));

	// keep the existing period, only restate the counts
	const period = (frm.doc.custom_reason || "").match(
		/(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})/
	);
	if (period) {
		frm.set_value(
			"custom_reason",
			__("Late entry deduction {0} to {1}: {2} late min over {3} day(s)", [
				period[1],
				period[2],
				minutes,
				rows.length,
			])
		);
	}
}

frappe.ui.form.on("Additional Salary", {
	// one row deleted, and the bulk "Delete" button over the checkboxes
	[LATE_TABLE + "_remove"]: function (frm) {
		chundakadan_sync_late_total(frm);
	},
	[LATE_TABLE + "_delete"]: function (frm) {
		chundakadan_sync_late_total(frm);
	},

	refresh(frm) {
		const grid = frm.get_field(LATE_TABLE) && frm.get_field(LATE_TABLE).grid;
		if (grid) grid.cannot_add_rows = true; // removal only, never invention

		if (frm.doc.docstatus !== 0) return; // only editable drafts

		frm.add_custom_button(__("Fetch Late Arrival Deduction"), function () {
			if (!frm.doc.employee) {
				frappe.msgprint(__("Select an Employee first."));
				return;
			}
			if (!frm.doc.payroll_date) {
				frappe.msgprint(
					__("Set the Payroll Date first — the whole month around it is used.")
				);
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
					frm.set_value(
						"custom_reason",
						__("Late entry deduction {0} to {1}: {2} late min over {3} day(s)", [
							d.from_date,
							d.to_date,
							d.total_minutes,
							d.late_days,
						])
					);
					// Setting salary_component triggers ERPNext's async
					// get_salary_component_amount, which overwrites `amount` with
					// the component default (0) AFTER we set it. Re-assert the
					// total once that async lookup has landed so ours wins.
					const apply_amount = () => frm.set_value("amount", d.total);
					apply_amount();
					setTimeout(function () {
						if (flt(frm.doc.amount) !== flt(d.total)) apply_amount();
					}, 800);
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
