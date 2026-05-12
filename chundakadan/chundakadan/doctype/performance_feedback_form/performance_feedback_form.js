// Copyright (c) 2026, Ashkar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Performance Feedback Form", {
	refresh(frm) {
		const instructions_html = `
			<div style="color: #000; line-height: 1.6; padding: 15px; background-color: #f8f9fa; border: 1px solid #d1d8dd; border-radius: 8px;">
				<h4 style="font-weight: bold; margin-bottom: 12px; margin-top: 0;">Instructions (keep this same everywhere):</h4>
				<ul style="list-style-type: disc; margin-left: 20px; font-size: 14px;">
					<li style="margin-bottom: 8px;">Rate each statement on a scale of <strong>1 to 5</strong>
						<ul style="list-style-type: circle; margin-left: 25px; margin-top: 5px;">
							<li>1 = Poor</li>
							<li>2 = Below Average</li>
							<li>3 = Satisfactory</li>
							<li>4 = Good</li>
							<li>5 = Excellent</li>
						</ul>
					</li>
					<li style="margin-bottom: 8px;">Be honest and objective</li>
					<li>Feedback will be used for performance improvement and development</li>
				</ul>
			</div>
		`;
		
		// Method 1: Set property
		frm.set_df_property('custom_instructions_keep_this_same_everywhere', 'options', instructions_html);
		
		// Method 2: Direct injection to wrapper
		if (frm.fields_dict.custom_instructions_keep_this_same_everywhere) {
			$(frm.fields_dict.custom_instructions_keep_this_same_everywhere.wrapper).html(instructions_html);
		}
	},
	custom_executive_name(frm) {

		if (frm.doc.custom_executive_name) {

			frappe.db.get_doc("Employee", frm.doc.custom_executive_name)
				.then((doc) => {

					// Employee Name
					frm.set_df_property(
						"custom_executive_name",
						"description",
						`Employee Name: <b>${doc.employee_name}</b>`
					);

					// Employee Code
					frm.set_value("custom_employee_code", doc.name);

					// Department
					frm.set_value("custom_departmentterritory", doc.department);
				});

		}
	}
});
