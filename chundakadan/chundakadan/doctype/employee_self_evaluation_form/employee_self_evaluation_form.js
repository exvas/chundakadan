// Copyright (c) 2026, Ashkar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Self Evaluation Form", {
	onload_post_render: function(frm) {
		if(cur_frm.is_new()){
			add_default_questions(cur_frm)
			add_default_categories(cur_frm)

		}

		cur_frm.set_df_property("significant_accomplishments","label","List your most significant accomplishment or contributions since last year. How do these achievements align with  the goals/objectives outlined for you?")
		cur_frm.set_df_property("duties_outside_regular_responsibilities","label","Since the last appraisal period, have you successfully performed any new tasks or additional duties outside the scope of your regular responsibilities? If so, please specify.")
		cur_frm.set_df_property("activities_initiated","label","What activities have you initiated, or actively participated into encourage camaraderie and team work within your group and/or office? What was the result?")
		cur_frm.set_df_property("professional_development_activities","label","Describe your professional development activities since last year, such as offsite seminars/classes (specify if selfdirected or required by your supervisor), onsite training, peer training, management coaching or mentoring, on-thejob experience, exposure to challenging projects, other—please describe")
		cur_frm.set_df_property("areas_requires_improvement","label","Describe areas you feel require improvement in terms of your professional capabilities. List the steps you plan to take and/or the resources you need to accomplish this?")
		cur_frm.set_df_property("career_goals","label","Identify two career goals for the coming year and indicate how you plan to accomplish them")
	},
});


function add_default_questions(cur_frm) {
	var questions = [
				"I know and understand the responsibilities of my job",
				"I know who is my supervisors and what their responsibilities are",
				"I feel that my workload is heavier than intends to be",
				"I feel that I can go to my supervisor with any problem that I may have",
				"I know what my benefits are",
				"I believe that I am productive in my job",
				"I believe that I am part of a productive and active team",
				"I know what my organization’s long-term goals are",
				"I am familiar with the organizational structure",
				"I believe that I have had enough training to perform my job",
			]

			for(var x=0;x<questions.length;x+=1){
				cur_frm.add_child("employee_self_evaluation_questions",{
					question: questions[x]
				})
				cur_frm.refresh_field("employee_self_evaluation_questions")
			}
}
function add_default_categories(cur_frm) {
	var categories = [
				"Technical Skills related to your specific job",
				"Technical Knowledge (up-to-date on industry /Discipline news, articles and best practices)",
				"Quality of Work Product (comprehensive,accurate, timely, etc.)",
				"Utilization or Productivity",
				"Business Developmen",
				"Management Skills",
				"Technology Skills",
				"Time Management& Organizational Skills",
				"Interpersonal Skills (positive attitude; ability to get along well with co- workers /clients /vendors)",
				"Communication Skills—Verbal/Written (proposals/reports, letters, e-mails, etc.)",
				"Innovation or Creativity",
				"Collaboration/Team work Skills",
				"Employee Policies (knowledgeable of and compliant with company policies and procedures)",
				"Leadership Skills (applies to anyone — not restricted to supervisory level employees)",
				"Professionalism (punctuality, attendance; conduct; responsiveness and follow through)",
				"Training and Other MKCD Program Attendance (% out of 100)",
				"Overall Rating",
			]

			for(var x=0;x<categories.length;x+=1){
				cur_frm.add_child("self_evaluation_categories",{
					category: categories[x]
				})
				cur_frm.refresh_field("self_evaluation_categories")
			}
}
