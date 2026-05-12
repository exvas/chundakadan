// Copyright (c) 2026, Ashkar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Self Assessment Form", {
	refresh(frm) {
		frm.trigger('render_instructions');
		frm.trigger('render_rating_table');
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
		if (frm.fields_dict.custom_instructions_keep_this_same_everywhere) {
			$(frm.fields_dict.custom_instructions_keep_this_same_everywhere.wrapper).html(instructions_html);
		}
	},
	render_rating_table(frm) {
		const questions = [
			{ field: 'meet_targets', label: 'I consistently meet my targets' },
			{ field: 'dealer_relationships', label: 'I maintain strong dealer relationships' },
			{ field: 'processes_reporting', label: 'I follow company processes and reporting' },
			{ field: 'handle_challenges', label: 'I handle challenges effectively' },
			{ field: 'contribute_team', label: 'I contribute to team success' }
		];

		let html = `
			<div style="font-family: 'Times New Roman', serif; color: #000; padding: 20px; background: #fff;">
				<h4 style="font-weight: bold; margin-bottom: 25px; font-size: 18px;">Rate the following:</h4>
				<table style="width: 100%; border-collapse: collapse; margin-bottom: 30px;">
					<tbody>
		`;

		questions.forEach((q, index) => {
			const current_val = frm.doc[q.field] || '';
			html += `
				<tr style="height: 50px; vertical-align: bottom;">
					<td style="width: 40px; font-size: 17px; padding-bottom: 10px;">${index + 1}.</td>
					<td style="font-size: 17px; padding-bottom: 10px;">${q.label}</td>
					<td style="width: 180px; text-align: right; padding-bottom: 10px;">
						<input type="number" min="1" max="5" value="${current_val}" 
							style="width: 60px; border: none; border-bottom: 1px solid #000; text-align: center; font-size: 17px; outline: none; background: transparent;"
							onchange="cur_frm.trigger('update_rating', '${q.field}', this.value)">
						<span style="font-size: 17px; margin-left: 5px;">/ 5</span>
					</td>
				</tr>
			`;
		});

		const overall = frm.doc.overall_self_rating || '';
		html += `
					</tbody>
				</table>
				<div style="margin-top: 40px; font-size: 20px; font-weight: bold;">
					Overall Self Rating: 
					<input type="number" min="1" max="5" value="${overall}" 
						style="width: 80px; border: none; border-bottom: 2px solid #000; text-align: center; font-size: 20px; font-weight: bold; outline: none; background: transparent;"
						onchange="cur_frm.trigger('update_rating', 'overall_self_rating', this.value)">
					<span style="font-size: 20px; margin-left: 5px;">/ 5</span>
				</div>
			</div>
		`;

		if (frm.fields_dict.rating_html) {
			$(frm.fields_dict.rating_html.wrapper).html(html);
		}
	},
	update_rating(frm, field, value) {
		let val = parseInt(value);
		if (isNaN(val) || val < 1) val = 0;
		if (val > 5) val = 5;
		
		frm.set_value(field, val);
	},
	custom_executive_name(frm) {
		if (frm.doc.custom_executive_name) {
			frappe.db.get_doc("Employee", frm.doc.custom_executive_name)
				.then((doc) => {
					frm.set_df_property("custom_executive_name", "description", `Employee Name: <b>${doc.employee_name}</b>`);
					frm.set_value("custom_employee_code", doc.name);
					frm.set_value("custom_departmentterritory", doc.department);
				});
		} else {
			frm.set_df_property("custom_executive_name", "description", "");
			frm.set_value("custom_employee_code", "");
			frm.set_value("custom_departmentterritory", "");
		}
	}
});
