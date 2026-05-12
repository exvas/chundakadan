// Copyright (c) 2026, Ashkar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Self Assessment Form", {
	refresh(frm) {
		frm.trigger('render_instructions');
	},
	render_instructions(frm) {
		const instructions_html = `
			<div style="color: #000; line-height: 1.6; padding: 15px; background-color: #f8f9fa; border: 1px solid #d1d8dd; border-radius: 8px;">
				<h4 style="font-weight: bold; margin-bottom: 12px; margin-top: 0;">Instructions (keep this same everywhere):</h4>
				<ul style="list-style-type: disc; margin-left: 20px; font-size: 14px;">
					<li style="margin-bottom: 8px;">Rate each statement on a scale of <strong>1 to 5</strong></li>
					<li style="margin-bottom: 8px;">Be honest and objective</li>
					<li>Feedback will be used for performance improvement and development</li>
				</ul>
			</div>
		`;
		if (frm.fields_dict.instructions) {
			$(frm.fields_dict.instructions.wrapper).html(instructions_html);
		}
	},
	executive_name(frm) {
		if (frm.doc.executive_name) {
			frappe.db.get_value("Employee", frm.doc.executive_name, ["name", "department", "employee_name"], (r) => {
				if (r) {
					frm.set_value("employee_code", r.name);
					frm.set_value("department_territory", r.department);
				}
			});
		} else {
			frm.set_value("employee_code", "");
			frm.set_value("department_territory", "");
		}
	}
});
