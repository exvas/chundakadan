// Custom JS for Exit Interview Form - V24 - PURE JS VERSION
console.log("Exit Interview Form JS V24 STARTING");

// HARD ALERT TO CONFIRM LOADING
frappe.msgprint({
    title: __('System Message'),
    indicator: 'blue',
    message: __('Exit Interview Script V24 Loaded Successfully. Triggering logic now.')
});

frappe.ui.form.on("Exit Interview Form", {
    refresh: function(frm) {
        console.log("V24: Refreshing Form");
        
        // Inject styles directly via JS to avoid HTML field template errors
        if (!$('#exit-v24-style').length) {
            $('<style id="exit-v24-style">').text(`
                .cb-mark, .rb-mark { display: none !important; }
                .cb-mark.is-active, .rb-mark.is-active { display: block !important; }
                .exit-survey-container { margin: 15px 0; border: 1px solid #d1d8dd; padding: 15px; border-radius: 8px; background: #fff; }
                .cb-row { display: flex; align-items: center; margin-bottom: 15px; cursor: pointer; }
                .cb-box { width: 22px; height: 22px; border: 2px solid #000; margin-right: 15px; display: flex; align-items: center; justify-content: center; }
                .cb-mark { width: 14px; height: 14px; background: #000; }
                .cb-label { font-weight: bold; font-size: 15px; }
            `).appendTo('head');
        }

        // Handle Checklist behavior
        $(document).off('click.v24').on('click.v24', '.cb-row', function(e) {
            if ($(e.target).is('input, textarea')) return;
            $(this).find('.cb-mark').toggleClass('is-active');
            console.log("Checkbox clicked");
        });
    },

    // AUTOMATIC FETCHING
    name1: function(frm) {
        if (!frm.doc.name1) {
            frm.set_value(['department', 'position', 'hire_date', 'separation_date'], '');
            return;
        }

        console.log("V24: name1 changed to", frm.doc.name1);
        frappe.show_alert({message: __('Fetching Employee Details...'), indicator: 'blue'});

        frappe.db.get_value('Employee', frm.doc.name1, ['department', 'designation', 'date_of_joining', 'date_of_retirement', 'relieving_date'], (r) => {
            if (r) {
                console.log("V24 Data Received:", r);
                frm.set_value('department', r.department);
                frm.set_value('position', r.designation);
                frm.set_value('hire_date', r.date_of_joining);
                
                // Set separation date (retirement or relieving)
                let sep = r.date_of_retirement || r.relieving_date;
                frm.set_value('separation_date', sep);
                
                frappe.show_alert({message: __('Employee data updated'), indicator: 'green'});
            }
        });
    }
});










