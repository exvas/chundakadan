import json
import frappe

# (label, filters) — number cards for the Display View workspace.
CARDS = [
    ("Total Display Units", [["Display Unit", "is_active", "=", 1]]),
    ("Displays In Warehouse", [["Display Unit", "current_location_type", "=", "Warehouse"]]),
    ("Displays At Customer", [["Display Unit", "current_location_type", "in", ["Customer", "Dealer", "Retail Outlet"]]]),
    ("Displays In Transit", [["Display Unit", "current_status", "=", "In Transit"]]),
    ("Displays Damaged", [["Display Unit", "current_status", "=", "Damaged"]]),
    ("Displays Missing", [["Display Unit", "current_status", "=", "Missing"]]),
    ("Displays Due for Return", [["Display Unit", "current_status", "=", "Installed at Customer"],
                                 ["Display Unit", "expected_return_date", "<=", "Today"]]),
]


def execute():
    for label, filters in CARDS:
        if frappe.db.exists("Number Card", label):
            continue
        frappe.get_doc({
            "doctype": "Number Card", "label": label, "type": "Document Type",
            "document_type": "Display Unit", "function": "Count",
            "filters_json": json.dumps(filters), "is_public": 1, "module": "Display Tracking",
        }).insert(ignore_permissions=True)
