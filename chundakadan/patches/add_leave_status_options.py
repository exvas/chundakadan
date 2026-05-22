import frappe


def execute():

    meta = frappe.get_doc(
        "DocField",
        {
            "parent": "Leave Application",
            "fieldname": "status"
        }
    )

    meta.options = "\n".join([
        "Open",
        "Pending",
        "Partially Approved",
        "Approved",
        "Rejected",
        "Draft",
        "Cancelled"
    ])

    meta.save()

    frappe.clear_cache()

    print("Status options updated")