import frappe


def execute():

    options = (
        "Open\n"
        "Pending\n"
        "Approved\n"
        "Rejected\n"
        "Cancelled"
    )

    ps_name = "Leave Application-status-options"

    if frappe.db.exists(
        "Property Setter",
        ps_name
    ):

        ps = frappe.get_doc(
            "Property Setter",
            ps_name
        )

        ps.value = options

        ps.save(
            ignore_permissions=True
        )

    else:

        frappe.get_doc({
            "doctype": "Property Setter",
            "doctype_or_field": "DocField",
            "doc_type": "Leave Application",
            "field_name": "status",
            "property": "options",
            "property_type": "Text",
            "value": options
        }).insert(
            ignore_permissions=True
        )

    frappe.clear_cache()