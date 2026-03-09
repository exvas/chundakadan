// Copyright (c) 2026, Ashkar and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Exit Interview Form", {
// 	refresh(frm) {

// 	},
// });
// Custom JS for Exit Interview Form - V24 - PURE JS VERSION
console.log("Exit Interview Form JS V24 STARTING");

frappe.ui.form.on("Exit Interview Form", {
    onload: function (frm) {
        console.log("Exit Interview Form: Loaded");
    },

    refresh: function (frm) {
        console.log("Exit Interview Form: Refreshing. DocStatus:", frm.doc.docstatus);

        // Ensure survey data is loaded when form is refreshed
        const load_data = () => {
            if (!frm.doc.survey_data) {
                console.log("No survey data found to load.");
                return;
            }

            try {
                const data = JSON.parse(frm.doc.survey_data);
                console.log("Loading survey data to HTML fields:", data);

                // 1. Load Checkboxes
                if (data.checkboxes) {
                    Object.keys(data.checkboxes).forEach(id => {
                        // Match by ID or Label text
                        let $cb = $(`input[type="checkbox"]#${id}`);
                        if ($cb.length === 0) {
                            // Try matching by label text if ID not found (for recommend section)
                            $('.recommend-options label').each(function () {
                                if ($(this).text().trim() === id) {
                                    $(this).find('input').prop('checked', data.checkboxes[id]);
                                }
                            });
                        } else {
                            $cb.prop('checked', data.checkboxes[id]);
                        }
                    });
                }

                // 2. Load Radio Buttons (Rating Tables)
                if (data.radios) {
                    Object.keys(data.radios).forEach(key => {
                        const [section, name, val] = key.split('|');
                        $(`[data-fieldname="${section}"] input[name="${name}"][value="${val}"]`).prop('checked', true);
                    });
                }

                // 3. Load Text Inputs/Textareas
                if (data.inputs) {
                    Object.keys(data.inputs).forEach(selector => {
                        $(selector).val(data.inputs[selector]);
                    });
                }
            } catch (e) {
                console.error("Critical: Error parsing survey data", e);
            }
        };

        // Initialize values for radio buttons if they don't have them
        $('.q-section table').each(function () {
            $(this).find('tr').each(function () {
                $(this).find('.rating-cell').each(function (i) {
                    // 5, 4, 3, 2, 1, N/A(0)
                    const val = (5 - i).toString();
                    if (val < 0) return; // ignore extra cells
                    $(this).find('input[type="radio"]').attr('value', i === 5 ? '0' : val);
                });
            });
        });

        // Use a short timeout to ensure the HTML fields are fully rendered in the DOM
        setTimeout(() => {
            load_data();

            // Handle recommend-options checkboxes as radio buttons
            $('.recommend-options input[type="checkbox"]').on('click', function () {
                if ($(this).is(':checked')) {
                    $('.recommend-options input[type="checkbox"]').not(this).prop('checked', false);
                }
            });
        }, 300);

        // Apply read-only state if document is submitted
        if (frm.doc.docstatus === 1) {
            console.log("Document is submitted. Disabling HTML survey fields.");
            $('.exit-survey-container input, .q-section input, .q-section textarea, .recommend-section input').prop('disabled', true);
        }
    },

    before_save: function (frm) {
        console.log("Capturing survey data before save...");
        const survey_data = {
            checkboxes: {},
            radios: {},
            inputs: {}
        };

        // Capture all checkboxes
        $('.exit-cb, .recommend-options input[type="checkbox"]').each(function () {
            const id = $(this).attr('id') || $(this).parent().text().trim();
            survey_data.checkboxes[id] = $(this).is(':checked');
        });

        // Capture all radio buttons
        $('.q-section').each(function () {
            const section = $(this).closest('[data-fieldname]').data('fieldname');
            $(this).find('input[type="radio"]:checked').each(function () {
                const name = $(this).attr('name');
                const val = $(this).attr('value');
                survey_data.radios[`${section}|${name}|${val}`] = true;
            });
        });

        // Capture textareas and inputs within specific sections
        $('.others-underline, .q-section textarea, .reason-input').each(function () {
            const section = $(this).closest('[data-fieldname]').data('fieldname');
            const type = $(this).is('textarea') ? 'textarea' : 'input';
            const selector = `[data-fieldname="${section}"] ${type}`;
            survey_data.inputs[selector] = $(this).val();
        });

        console.log("Survey data captured:", survey_data);
        frm.set_value('survey_data', JSON.stringify(survey_data));
    },

    // AUTOMATIC FETCHING Logic for Employee Details
    name1: function (frm) {
        if (!frm.doc.name1) {
            frm.set_value('department', '');
            frm.set_value('position', '');
            frm.set_value('hire_date', '');
            frm.set_value('separation_date', '');
            return;
        }

        console.log("V24: name1 changed to", frm.doc.name1);
        // frappe.show_alert({message: __('Fetching Employee Details...'), indicator: 'blue'});

        frappe.db.get_value('Employee', frm.doc.name1, ['department', 'designation', 'date_of_joining', 'date_of_retirement', 'relieving_date'], (r) => {
            if (r) {
                console.log("V24 Data Received:", r);
                frm.set_value('department', r.department);
                frm.set_value('position', r.designation);
                frm.set_value('hire_date', r.date_of_joining);

                // Set separation date from relieving_date
                frm.set_value('separation_date', r.relieving_date);

                // frappe.show_alert({ message: __('Employee data updated'), indicator: 'green' });
            }
        });
    }
});










