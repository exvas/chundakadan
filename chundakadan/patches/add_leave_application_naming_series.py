import frappe


def execute():
    # Naming series options to add
    new_series = [
        "SI-.YY.-.####",
        "SR-.YY.-.####"
    ]

    # Property Setter for options
    ps_name = "Leave Application-naming_series-options"

    if frappe.db.exists("Property Setter", ps_name):
        ps = frappe.get_doc("Property Setter", ps_name)

        current_options = (ps.value or "").split("\n")

        changed = False
        for s in new_series:
            if s not in current_options:
                current_options.append(s)
                changed = True

        if changed:
            ps.value = "\n".join(filter(None, current_options))
            ps.save(ignore_permissions=True)

    else:
        frappe.get_doc({
            "doctype": "Property Setter",
            "name": ps_name,
            "doctype_or_field": "DocField",
            "doc_type": "Leave Application",
            "field_name": "naming_series",
            "property": "options",
            "property_type": "Text",
            "value": "\n".join(new_series),
            "module": "Chundakadan"
        }).insert(ignore_permissions=True)

    # Default naming series setter
    default_ps = "Leave Application-naming_series-default"

    if frappe.db.exists("Property Setter", default_ps):
        ps = frappe.get_doc("Property Setter", default_ps)

        if ps.value != "SI-.YY.-.####":
            ps.value = "SI-.YY.-.####"
            ps.save(ignore_permissions=True)

    else:
        frappe.get_doc({
            "doctype": "Property Setter",
            "name": default_ps,
            "doctype_or_field": "DocField",
            "doc_type": "Leave Application",
            "field_name": "naming_series",
            "property": "default",
            "property_type": "Text",
            "value": "SI-.YY.-.####",
            "module": "Chundakadan"
        }).insert(ignore_permissions=True)

    frappe.clear_cache()