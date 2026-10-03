// Copyright (c) 2026, Chundakadan and contributors
frappe.ui.form.on("Daily Work Summary", {
	refresh(frm) {
		// The chain is the GM alone, so the only step is index 0 and the only
		// remark is the GM's. hod_remarks is retired: read-only in the doctype
		// and hidden unless an older summary already carries one.
		frm.set_df_property("gm_remarks", "read_only", !step_is_mine(frm, 0));

		if (frm.doc.custom_approval_status === "Returned" && frm.doc.return_reason) {
			frm.dashboard.set_headline_alert(
				__("Returned for correction: {0}", [frm.doc.return_reason]),
				"orange"
			);
		}
		if (frm.is_new()) return;

		// Say where it stands, always. A draft otherwise shows nothing at all --
		// the remark boxes and the flow table are empty and Frappe hides them --
		// which reads as "the approval disappeared".
		show_where_it_stands(frm);

		if (frm.doc.docstatus !== 0) return;

		const draft = ["Draft", "Returned"].includes(frm.doc.custom_approval_status);
		if (!draft && waiting_on_me(frm)) {
			frm.add_custom_button(__("Return for Correction"), () => send_back(frm));
		}

		// Submit is refused by the server -- the GM closes this through the
		// chain -- so don't offer a button that cannot work. While there are
		// unsaved changes Frappe's own Save must stay the primary action.
		if (frm.is_dirty()) return;
		frm.page.clear_primary_action();
		if (!draft && waiting_on_me(frm)) {
			frm.page.set_primary_action(__("Add Remarks & Close"), () => remark(frm));
		}
	},
});

function show_where_it_stands(frm) {
	const status = frm.doc.custom_approval_status;
	if (frm.doc.docstatus === 1 || status === "Approved") {
		frm.dashboard.set_headline_alert(__("Closed by the General Manager"), "green");
		return;
	}
	if (status === "Pending" || status === "Partially Approved") {
		frm.dashboard.set_headline_alert(
			__("Waiting on {0}", [frm.doc.current_approver || __("the General Manager")]),
			"blue"
		);
		return;
	}
	if (status === "Draft") {
		// saving a summary that has work in it puts it with the GM, so a
		// draft at this point means the day's tasks are still empty
		frm.dashboard.set_headline_alert(
			__("Add the day's tasks and save — that puts this in front of the General Manager"),
			"orange"
		);
	}
}

function waiting_on_me(frm) {
	if (frm.doc.current_approver === frappe.session.user) return true;
	const row = (frm.doc.approval_flow || [])[frm.doc.current_approval_index || 0];
	return !!row && frappe.user_roles.includes(row.approver_role);
}

// Only the approver standing at that step may type in that remark box.
// With a one-step chain the index is always 0.
function step_is_mine(frm, index) {
	if (frm.doc.docstatus !== 0) return false;
	if ((frm.doc.current_approval_index || 0) !== index) return false;
	return waiting_on_me(frm);
}

function remark(frm) {
	const label = __("GM Remarks");
	frappe.prompt(
		[{ fieldname: "remarks", label: label, fieldtype: "Small Text", reqd: 1 }],
		(values) => {
			frappe
				.xcall("chundakadan.chundakadan.api.work_summary.add_remarks", {
					docname: frm.doc.name,
					remarks: values.remarks,
				})
				.then((r) => {
					frappe.show_alert({
						message:
							r.status === "Approved"
								? __("Summary closed")
								: __("Passed to {0}", [r.current_approver]),
						indicator: "green",
					});
					frm.reload_doc();
				});
		},
		label,
		__("Submit")
	);
}

function send_back(frm) {
	frappe.prompt(
		[{ fieldname: "reason", label: __("What needs correcting?"), fieldtype: "Small Text", reqd: 1 }],
		(values) => {
			frappe
				.xcall("chundakadan.chundakadan.api.work_summary.return_for_correction", {
					docname: frm.doc.name,
					reason: values.reason,
				})
				.then(() => {
					frappe.show_alert({ message: __("Returned to the employee"), indicator: "orange" });
					frm.reload_doc();
				});
		},
		__("Return for Correction"),
		__("Return")
	);
}
