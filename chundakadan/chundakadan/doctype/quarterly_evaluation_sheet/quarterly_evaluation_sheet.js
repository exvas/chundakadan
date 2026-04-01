// Copyright (c) 2026, Ashkar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Quarterly Evaluation Sheet", {
	refresh: function () {
		if(cur_frm.is_new()){
			add_default_criterion(cur_frm)
			add_default_metrics(cur_frm)
		}
	cur_frm.set_intro('<b>Quarterly Evaluation Sheet for Best Performer Award - Sales Executives</b><br>' +
		'<p>This evaluation sheet is designed to assess Field Sales Executives performance from April to July (Q2 extended quarter) for ' +
		'selecting the Best Performer Award. Supervisors or evaluators should rate each employee based on the qualitative criteria below' +
		' using a scale of 1-5 (1 = Poor, 2 = Below Average, 3 = Average, 4 = Above Average, 5 = Excellent). Additionally, record ' +
		'quantitative metrics such as total sales, collections, leads generated, etc. Calculate the total qualitative score and ' +
		'combine with quantitative achievements for overall assessment. The executive with the highest combined performance ' +
		'(considering both scores and metrics) may be nominated. Submit completed sheets to HR by the end of the evaluation period</p>');
	}
});

frappe.ui.form.on("Quarterly Evaluation Sheet Metrics", {
	actual_achievement: function(frm,cdt,cdn) {
		var row = locals[cdt][cdn]
		 calculate_achievement_percentage(row,cur_frm)
	},
	target: function(frm,cdt,cdn) {
		var row = locals[cdt][cdn]
		calculate_achievement_percentage(row,cur_frm)
	},
	// quarterly_evaluation_sheet_metrics_remove: function (frm) {
	// 	 calculate_metrics_total(frm)
	// }
});
function calculate_achievement_percentage(row,cur_frm) {
	 	row.achievement_percentage = row.target > 0 ? (row.actual_achievement / row.target) * 100 : 0
		cur_frm.refresh_field("quarterly_evaluation_sheet_metrics")


}

frappe.ui.form.on("Quarterly Evaluation Sheet Criteria", {
	rating: function(frm,cdt,cdn) {
		calculate_criteria_total(frm)
	},
	quarterly_evaluation_sheet_criteria_remove: function (frm) {
		calculate_criteria_total(frm)
	}
});

function calculate_criteria_total(frm) {
    let total = 0;

    (frm.doc.quarterly_evaluation_sheet_criteria || []).forEach(row => {
    	if(row.rating){
    		 total += parseInt(row.rating) || 0;
		}

    });
    let total_score = frm.doc.quarterly_evaluation_sheet_criteria.length > 0 ?
						total / (5 * frm.doc.quarterly_evaluation_sheet_criteria.length) :
						0
	let average = frm.doc.quarterly_evaluation_sheet_criteria.length > 0 ? (total_score / frm.doc.quarterly_evaluation_sheet_criteria.length) : 0
	frm.set_value('total_qualitative_score',total_score)
	frm.set_value('average_qualitative_score',average)
}

function add_default_criterion(cur_frm) {
	var criterions = [
		{
			criterion: "Job Knowledge & Skills",
			description: "Demonstrates strong understanding of products/services, sales techniques, market trends, and CRM tools."
		},
		{
			criterion: "Productivity & Efficiency",
			description: "Manages time effectively in the field, prioritizes high-potential leads, and maximizes daily visits/calls."
		},
		{
			criterion: "Attendance & Punctuality",
			description: "Maintains consistent field presence, adheres to schedules, and reports on time."
		},
		{
			criterion: "Initiative & Problem-Solving",
			description: "Proactively identifies new opportunities, overcomes objections, and resolves client issues independently"
		},
		{
			criterion: "Teamwork & Collaboration",
			description: "Coordinates with internal teams (e.g., support, marketing) and shares best practices with peers."
		},
		{
			criterion: "Customer Service & Relationship Building",
			description: "Builds strong client relationships, provides excellent follow-up, andhandles complaints professionally."
		},
		{
			criterion: "Attention to Detail & Accuracy",
			description: "Ensures accurate reporting of sales data, contracts, and client information"
		},
		{
			criterion: "Adaptability & Flexibility",
			description: "Adjusts to changing market conditions, territory shifts, or new sales targets with ease"
		},
		{
			criterion: "Professionalism & Attitude",
			description: "Maintains a positive, ethical approach in client interactions and represents the company well."
		},
		{
			criterion: "Overall Contribution",
			description: "Goes above and beyond to drive sales growth, mentor others, or contribute to team success"
		},
	]

			for(var x=0;x<criterions.length;x+=1){
				cur_frm.add_child("quarterly_evaluation_sheet_criteria",criterions[x])
				cur_frm.refresh_field("quarterly_evaluation_sheet_criteria")
			}
}
function add_default_metrics(cur_frm) {
	var metrics = [
		{
			metric: "Total Sales",
			description: "Total revenue generated from sales"
		},
		{
			metric: "Collections",
			description: "Total amount collected from clients (e.g., payments received)."
		},
		{
			metric: "Leads Generated",
			description: "Number of new leads/prospects identified and qualified."
		},
		{
			metric: "Conversion Rate",
			description: "Percentage of leads converted to sales."
		},
		{
			metric: "ClientVisits/Calls",
			description: "Total number of field visits or calls made."
		},
		{
			metric: "New Clients Acquired",
			description: "Number of new client’s on boarded"
		},
		{
			metric: "Repeat Business",
			description: "Revenue from existing clients or repeat orders."
		},
		{
			metric: "Pipeline Value",
			description: "Estimated value of ongoing deals in the sales pipeline."
		}
	]

			for(var x=0;x<metrics.length;x+=1){
				cur_frm.add_child("quarterly_evaluation_sheet_metrics",metrics[x])
				cur_frm.refresh_field("quarterly_evaluation_sheet_metrics")
			}
}
