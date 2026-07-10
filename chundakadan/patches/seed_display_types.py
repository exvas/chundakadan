import frappe

TYPES = ["Display Rack", "Display Shelf", "Display Stand", "Cooler",
         "Branding Material", "Promotional Display"]


def execute():
    for t in TYPES:
        if not frappe.db.exists("Display Type", t):
            frappe.get_doc({"doctype": "Display Type", "type_name": t}).insert(ignore_permissions=True)
