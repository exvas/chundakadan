import frappe

def execute():
    field = frappe.get_meta("Leave Application").get_field("status")

    options = field.options.split("\n")

    if "Partially Approved" not in options:
        insert_after = "Approved"

        if insert_after in options:
            idx = options.index(insert_after)
            options.insert(idx + 1, "Partially Approved")
        else:
            options.append("Partially Approved")

        frappe.make_property_setter(
            {
                "doctype": "Leave Application",
                "fieldname": "status",
                "property": "options",
                "value": "\n".join(options),
                "property_type": "Text",
            }
        )