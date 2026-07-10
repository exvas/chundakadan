frappe.listview_settings["Display Unit"] = {
    add_fields: ["current_status", "current_location_type"],
    get_indicator: function (doc) {
        const map = {
            "At Supplier": "purple",
            "In Warehouse": "blue",
            "Reserved": "cyan",
            "In Transit": "orange",
            "Installed at Customer": "green",
            "Returned": "light-blue",
            "Damaged": "red",
            "Missing": "red",
            "Under Repair": "orange",
            "Returned to Supplier": "gray",
        };
        const color = map[doc.current_status] || "gray";
        return [__(doc.current_status), color,
                "current_status,=," + doc.current_status];
    },
};
