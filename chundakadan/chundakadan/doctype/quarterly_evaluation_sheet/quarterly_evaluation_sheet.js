// Copyright (c) 2026, Ashkar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Quarterly Evaluation Sheet", {
	refresh: function () {
	cur_frm.set_intro('<b>Quarterly Evaluation Sheet for Best Performer Award - Sales Executives</b><br>' +
		'<p>This evaluation sheet is designed to assess Field Sales Executives performance for ' +
		'selecting the Best Performer Award. Supervisors or evaluators should rate each employee based on the qualitative criteria below' +
		' using a scale of 1-5 (1 = Poor, 2 = Below Average, 3 = Average, 4 = Above Average, 5 = Excellent). Additionally, record ' +
		'quantitative metrics such as total sales, collections, leads generated, etc. Calculate the total qualitative score and ' +
		'combine with quantitative achievements for overall assessment. The executive with the highest combined performance ' +
		'(considering both scores and metrics) may be nominated. Submit completed sheets to HR by the end of the evaluation period</p>');
	},
	quarter: function(frm) {
		if(cur_frm.doc.quarter){
			cur_frm.call({
				doc: cur_frm.doc,
				method: "set_evaluation_range_date",
				freeze: true,
				freeze_message: "Setting Evaluation Dates",
				callback: function () {

				}
			})
		}
	},
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
