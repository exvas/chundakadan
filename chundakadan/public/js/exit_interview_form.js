// Custom JS for Exit Interview Form - V17
console.log("Exit Interview Form JS V17 Active");

(function() {
    // Handling Survey Checkboxes (cb-box) - Toggle behavior
    $(document).on('click', '.cb-box, .cb-row', function(e) {
        // Skip if clicking inside the "others" input
        if ($(e.target).is('input.others-underline, textarea')) return;
        
        const $row = $(this).closest('.cb-row');
        const $mark = $row.find('.cb-mark');
        
        if ($mark.length) {
            $mark.toggleClass('is-active');
            console.log("Survey checkbox toggled");
        }
        
        e.preventDefault();
        e.stopPropagation();
    });

    // Handling Rating Boxes (rb-box) - Radio behavior within a row
    $(document).on('click', '.rb-box', function(e) {
        const rowId = $(this).attr('data-row');
        const $mark = $(this).find('.rb-mark');
        
        if ($mark.length) {
            // Hide all marks in the same row
            $(this).closest('tr').find('.rb-mark').removeClass('is-active');
            // Show this one
            $mark.addClass('is-active');
            console.log("Rating selected for row " + rowId);
        }
        
        e.preventDefault();
        e.stopPropagation();
    });
})();

frappe.ui.form.on("Exit Interview Form", {
    refresh: function(frm) {
        console.log("V17 Refresh Triggered");
        
        // Inject CSS to handle the 'is-active' class visibility
        const customStyles = `
            .cb-mark, .rb-mark { display: none !important; }
            .cb-mark.is-active, .rb-mark.is-active { display: block !important; }
        `;
        
        if (!$('#exit-form-v17-styles').length) {
            // Remove any old styles if they exist
            $('style[id^="exit-form-custom-style"]').remove();
            $('<style id="exit-form-v17-styles">').text(customStyles).appendTo('head');
        }
    }
});





