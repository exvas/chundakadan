import frappe


def execute():

    docs = [
        "HR-LAP-2026-00062",
        "HR-LAP-2026-00136",
        "HR-LAP-2026-00135",
        "HR-LAP-2026-00141",
    ]

    for docname in docs:

        frappe.db.set_value(
            "Leave Application",
            docname,
            "status",
            "Partially Approved",
            update_modified=False
        )

        print(
            f"{docname} -> Partially Approved"
        )

    frappe.db.commit()

    print("Done")