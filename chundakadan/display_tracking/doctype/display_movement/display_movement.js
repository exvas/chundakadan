// Populate the Dynamic Link companion doctype for `to_location` when the
// location type changes. Frappe validates links before any server hook, so
// this must be set client-side (desk) before save.
frappe.ui.form.on("Display Movement", {
    to_location_type: function (frm) {
        const map = {
            "Warehouse": "Warehouse Rack",
            "Customer": "Customer", "Dealer": "Customer", "Retail Outlet": "Customer",
            "Service Center": "Display Service Center",
            "Supplier": "Supplier",
        };
        frm.set_value("to_location_doctype", map[frm.doc.to_location_type] || "");
        frm.set_value("to_location", null);
    },
    display_unit: function (frm) {
        // Show the unit's current status to the user for context.
        if (frm.doc.display_unit) {
            frappe.db.get_value("Display Unit", frm.doc.display_unit, "current_status")
                .then(r => {
                    if (r && r.message) {
                        frm.dashboard.set_headline(
                            __("Current status: {0}", [r.message.current_status]));
                    }
                });
        }
    },
});
