import frappe

def execute():
    # Delete the incorrect property setters created for Leave Application naming series
    incorrect_setters = [
        "Leave Application-naming_series-options",
        "Leave Application-naming_series-default"
    ]
    for ps_name in incorrect_setters:
        if frappe.db.exists("Property Setter", ps_name):
            frappe.delete_doc("Property Setter", ps_name, ignore_permissions=True)
            print(f"Deleted Property Setter: {ps_name}")

    frappe.clear_cache(doctype="Leave Application")
    frappe.db.commit()
