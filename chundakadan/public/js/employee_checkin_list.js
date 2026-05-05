frappe.listview_settings["Employee Checkin"] = {
    onload: function(listview) {
        setTimeout(() => {
            listview.$result.find('[data-fieldname="status"]').hide();
        }, 100);
    }
};