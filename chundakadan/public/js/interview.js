frappe.ui.form.on("Interview", {
	job_applicant: function (frm) {
		if (!frm.doc.job_applicant) {
			frm.set_value("custom_applicant_name", "");
			return;
		}
		frappe.db.get_value("Job Applicant", frm.doc.job_applicant, "applicant_name").then((r) => {
			if (r.message) {
				frm.set_value("custom_applicant_name", r.message.applicant_name);
			}
		});
	},
});
