// Copyright (c) 2025, TBO Cloud and contributors
// For license information, please see license.txt

frappe.ui.form.on('Cleaning Checklist', {
	refresh: function(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status !== 'Completed') {
			frm.add_custom_button(__('Mark as Completed'), function() {
				frappe.call({
					method: 'frappe.client.set_value',
					args: {
						doctype: 'Cleaning Checklist',
						name: frm.doc.name,
						fieldname: 'status',
						value: 'Completed'
					},
					callback: function(r) {
						frm.reload_doc();
					}
				});
			});
		}
		
		// Add quick filter buttons
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Add Office Area Tasks'), function() {
				add_default_tasks(frm, 'Office Area');
			});
			
			frm.add_custom_button(__('Add Dispatch & Warehouse Tasks'), function() {
				add_default_tasks(frm, 'Dispatch & Ware house');
			});
			
			frm.add_custom_button(__('Add Pantry & Washroom Tasks'), function() {
				add_default_tasks(frm, 'Pantry & Washroom');
			});
		}
	},
	
	date: function(frm) {
		// Highlight current day column in child table
		highlight_current_day(frm);
	}
});

frappe.ui.form.on('Cleaning Checklist Item', {
	area: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		// Auto-populate common cleaning types based on area
		if (row.area && !row.cleaning_type) {
			let suggestions = get_cleaning_suggestions(row.area);
			if (suggestions.length > 0) {
				frappe.msgprint(__('Common tasks for {0}: {1}', [row.area, suggestions.join(', ')]));
			}
		}
	}
});

function add_default_tasks(frm, area) {
	let tasks = get_default_tasks(area);
	tasks.forEach(task => {
		let row = frm.add_child('cleaning_items');
		row.area = area;
		row.frequency = task.frequency;
		row.cleaning_type = task.name;
	});
	frm.refresh_field('cleaning_items');
}

function get_default_tasks(area) {
	if (area === 'Office Area') {
		return [
			{name: 'Dust Furniture, desks, chair, Cabinets', frequency: 'Daily'},
			{name: 'Empty waste containers', frequency: 'Daily'},
			{name: 'Cleaning Entrance and Glass & Doors', frequency: 'Daily'},
			{name: 'Dust & mop Floor', frequency: 'Daily'},
			{name: 'Dust window & curtains', frequency: 'Weekly'},
			{name: 'Clean Hanging lights', frequency: 'Weekly'},
			{name: 'Dust Keyboards, Monitors & telephone', frequency: 'Weekly'},
			{name: 'AC', frequency: 'Weekly'}
		];
	} else if (area === 'Dispatch & Ware house') {
		return [
			{name: 'Dust & Mop Floor', frequency: 'Daily'},
			{name: 'Empty waste containers', frequency: 'Daily'},
			{name: 'Dust rack path way', frequency: 'Daily'},
			{name: 'Prayer Room', frequency: 'Daily'}
		];
	} else if (area === 'Pantry & Washroom') {
		return [
			{name: 'Floor cleaning', frequency: 'Daily'},
			{name: 'Wash Basin', frequency: 'Daily'},
			{name: 'Toilets', frequency: 'Daily'},
			{name: 'Pantry Desk & Chair', frequency: 'Daily'}
		];
	}
	return [];
}

function get_cleaning_suggestions(area) {
	let tasks = get_default_tasks(area);
	return tasks.map(t => t.name);
}

function highlight_current_day(frm) {
	if (frm.doc.date) {
		let date = frappe.datetime.str_to_obj(frm.doc.date);
		let day = date.getDay(); // 0 = Sunday, 1 = Monday, etc.
		let days = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
		let current_day = days[day];
		
		// This is a visual hint - actual logic would need custom styling
		console.log('Current day for checklist:', current_day);
	}
}
