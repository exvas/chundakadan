// Copyright (c) 2026, Ashkar and contributors
// Employee Checkin is fully READ-ONLY. Check-in time can only be corrected via
// the HR-gated "Update Time" button, which logs the change + emails the
// Chundakadan Settings recipients and the affected employee.

const CHECKIN_EDIT_ROLES = ["HR User", "HR Manager", "System Manager", "Administrator"];

frappe.ui.form.on("Employee Checkin", {
	refresh(frm) {
		// lock every field + block save so nothing is edited directly
		(frm.meta.fields || []).forEach((f) => {
			if (!["Section Break", "Column Break", "HTML"].includes(f.fieldtype)) {
				frm.set_df_property(f.fieldname, "read_only", 1);
			}
		});
		frm.disable_save();

		if (frm.doc.__islocal) return;
		if (!frappe.user.has_role(CHECKIN_EDIT_ROLES)) return;

		frm.add_custom_button(__("Update Time"), () => open_update_time_dialog(frm));
	},
});

function open_update_time_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Update Check-in Time"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "info",
				options: `<div class="text-muted" style="margin-bottom:8px">${__(
					"Correcting the check-in time for <b>{0}</b>. Current: <b>{1}</b>. A notification email is sent to HR and the employee.",
					[frappe.utils.escape_html(frm.doc.employee_name || frm.doc.employee), frm.doc.time]
				)}</div>`,
			},
			{
				fieldtype: "Datetime",
				fieldname: "new_time",
				label: __("New Time"),
				reqd: 1,
				default: frm.doc.time,
			},
			{
				fieldtype: "Small Text",
				fieldname: "reason",
				label: __("Reason"),
				reqd: 1,
			},
		],
		primary_action_label: __("Update & Notify"),
		primary_action(values) {
			frappe.call({
				method: "chundakadan.doc_events.employee_checkin.update_checkin_time",
				args: { checkin: frm.doc.name, new_time: values.new_time, reason: values.reason },
				freeze: true,
				freeze_message: __("Updating time & sending notification..."),
				callback(r) {
					if (!r.message) return;
					d.hide();
					frappe.show_alert(
						{
							message: __("Time updated {0} → {1}. Notification sent.", [
								r.message.old,
								r.message.new,
							]),
							indicator: "green",
						},
						7
					);
					frm.reload_doc();
				},
			});
		},
	});
	d.show();
}
