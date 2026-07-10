frappe.listview_settings["Display Movement"] = {
    add_fields: ["docstatus", "movement_type", "to_status"],
    get_indicator: function (doc) {
        // Cancelled movements are the audit reversals — make them obvious.
        if (doc.docstatus === 2) {
            return [__("Cancelled"), "red", "docstatus,=,2"];
        }
        if (doc.docstatus === 0) {
            return [__("Draft"), "gray", "docstatus,=,0"];
        }
        return [__(doc.movement_type), "green", "docstatus,=,1"];
    },
};
