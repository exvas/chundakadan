import json
import frappe

# (label, filters, dynamic_filters) — number cards for the Display View workspace.
# dynamic_filters values are Python expressions evaluated at render time.
CARDS = [
    ("Total Display Units", [["Display Unit", "is_active", "=", 1]], None),
    ("Displays In Warehouse", [["Display Unit", "current_location_type", "=", "Warehouse"]], None),
    ("Displays At Customer", [["Display Unit", "current_location_type", "in", ["Customer", "Dealer", "Retail Outlet"]]], None),
    ("Displays In Transit", [["Display Unit", "current_status", "=", "In Transit"]], None),
    ("Displays Damaged", [["Display Unit", "current_status", "=", "Damaged"]], None),
    ("Displays Missing", [["Display Unit", "current_status", "=", "Missing"]], None),
    ("Displays Due for Return",
        [["Display Unit", "current_status", "=", "Installed at Customer"]],
        [["Display Unit", "expected_return_date", "<=", "frappe.utils.nowdate()"]]),
]


def execute():
    for label, filters, dynamic in CARDS:
        if frappe.db.exists("Number Card", label):
            # keep existing cards in sync with the dynamic-filter fix
            frappe.db.set_value("Number Card", label, {
                "filters_json": json.dumps(filters),
                "dynamic_filters_json": json.dumps(dynamic) if dynamic else None,
            })
            continue
        frappe.get_doc({
            "doctype": "Number Card", "label": label, "type": "Document Type",
            "document_type": "Display Unit", "function": "Count",
            "filters_json": json.dumps(filters),
            "dynamic_filters_json": json.dumps(dynamic) if dynamic else None,
            "is_public": 1, "module": "Display Tracking",
        }).insert(ignore_permissions=True)
