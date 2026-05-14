// Copyright (c) 2026, Ashkar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Period Salary Slip", {
	refresh(frm) {
		// Hide the standard Actions dropdown — not needed for this DocType
		frm.page.wrapper.find(".actions-btn-group").hide();

		// Always show Fetch Salary Slips
		let fetch_btn = frm.add_custom_button(__("Fetch Salary Slips"), () => fetch_salary_slips(frm));
		fetch_btn.html('<i class="fa fa-refresh" style="margin-right: 5px;"></i> ' + __("Fetch Salary Slips"));
		fetch_btn.removeClass('btn-default').addClass('btn-primary');

		// Show View Print button only when salary slips are loaded
		if (frm.doc.salary_slips && frm.doc.salary_slips.length) {
			let print_btn = frm.add_custom_button(__("View Print"), () => view_print_dialog(frm));
			print_btn.html('<i class="fa fa-eye" style="margin-right: 5px;"></i> ' + __("View Print"));
			print_btn.removeClass('btn-default').addClass('btn-secondary');
		}
	},

	from_date(frm) {
		validate_date_range(frm);
	},

	to_date(frm) {
		validate_date_range(frm);
	},
});

// ─── Validation ────────────────────────────────────────────────────────────────

function validate_date_range(frm) {
	if (frm.doc.from_date && frm.doc.to_date) {
		if (frm.doc.from_date > frm.doc.to_date) {
			frappe.msgprint({
				title: __("Invalid Date Range"),
				message: __("From Date cannot be later than To Date."),
				indicator: "red",
			});
			frm.set_value("to_date", "");
		}
	}
}

// ─── Fetch Salary Slips ─────────────────────────────────────────────────────

function fetch_salary_slips(frm) {
	if (!frm.doc.employee) {
		frappe.msgprint({ title: __("Missing Field"), message: __("Please select an Employee."), indicator: "orange" });
		return;
	}
	if (!frm.doc.from_date) {
		frappe.msgprint({ title: __("Missing Field"), message: __("Please set the From Date."), indicator: "orange" });
		return;
	}
	if (!frm.doc.to_date) {
		frappe.msgprint({ title: __("Missing Field"), message: __("Please set the To Date."), indicator: "orange" });
		return;
	}
	if (frm.doc.from_date > frm.doc.to_date) {
		frappe.msgprint({ title: __("Invalid Date Range"), message: __("From Date cannot be later than To Date."), indicator: "red" });
		return;
	}

	frappe.call({
		method: "chundakadan.chundakadan.api.period_salary_slip.get_salary_slips",
		args: {
			employee: frm.doc.employee,
			from_date: frm.doc.from_date,
			to_date: frm.doc.to_date,
		},
		freeze: true,
		freeze_message: __("Fetching Salary Slips..."),
		callback(r) {
			frm.clear_table("salary_slips");

			if (!r.message || r.message.length === 0) {
				frappe.msgprint({
					title: __("No Records Found"),
					message: __("No submitted salary slips found for the selected employee and date range."),
					indicator: "blue",
				});
				frm.refresh_field("salary_slips");
				return;
			}

			r.message.forEach((slip) => {
				let row = frm.add_child("salary_slips");
				row.salary_slip = slip.salary_slip;
				row.start_date  = slip.start_date;
				row.end_date    = slip.end_date;
				row.net_pay     = slip.net_pay;
			});

			frm.refresh_field("salary_slips");
			frm.refresh(); // re-render toolbar to show View Print button

			frappe.show_alert({
				message: __("{0} salary slip(s) fetched successfully.", [r.message.length]),
				indicator: "green",
			});
		},
	});
}

// ─── View Print Dialog ──────────────────────────────────────────────────────

function view_print_dialog(frm) {
	if (!frm.doc.name || frm.doc.__islocal) {
		frappe.msgprint({
			title: __("Save Required"),
			message: __("Please save the document before viewing the print."),
			indicator: "orange",
		});
		return;
	}

	// Build the Frappe printview URL
	const print_url = "/printview?" + $.param({
		doctype : "Period Salary Slip",
		name    : frm.doc.name,
		format  : "Period Salary Slip",
		no_letterhead: 1,
		_lang   : frappe.boot.lang || "en",
	});

	const iframe_html = `
		<div style="height: 65vh; width: 100%; border: 1px solid #d1d8dd; border-radius: 4px; overflow: hidden;">
			<iframe src="${print_url}" frameborder="0" style="width: 100%; height: 100%;"></iframe>
		</div>`;

	const d = new frappe.ui.Dialog({
		title: __("Print Preview — {0} ({1} to {2})", [
			frm.doc.employee_name || frm.doc.employee,
			frappe.datetime.str_to_user(frm.doc.from_date),
			frappe.datetime.str_to_user(frm.doc.to_date),
		]),
		size: "extra-large",
		fields: [
			{ fieldtype: "HTML", fieldname: "print_preview", options: iframe_html },
		],
		primary_action_label: __("🖨 Open in New Tab"),
		primary_action() {
			// Open print preview in new tab
			window.open(print_url, "_blank");
			d.hide();
		},
		secondary_action_label: __("Close"),
		secondary_action() {
			d.hide();
		},
	});

	d.show();
}

// Helper — format number as currency string
function format_currency(amount) {
	if (!amount) return "0.00";
	return parseFloat(amount).toLocaleString("en-IN", {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	});
}
