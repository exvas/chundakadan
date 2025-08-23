// file: item_price_comparison.js

frappe.query_reports["Item Price Comparison"] = {
    "filters": [
        {
            "fieldname": "item_code",
            "label": __("Item Code"),
            "fieldtype": "Link",
            "options": "Item",
            "width": "120"
        },
        {
            "fieldname": "item_name",
            "label": __("Item Name"),
            "fieldtype": "Data",
            "width": "120"
        },
        {
            "fieldname": "item_group",
            "label": __("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group",
            "width": "120"
        },
        {
            "fieldname": "stock_uom",
            "label": __("UOM"),
            "fieldtype": "Link",
            "options": "UOM",
            "width": "100"
        },
        {
            "fieldname": "warehouse",
            "label": __("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": "120"
        }
    ]
};
