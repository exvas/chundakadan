import frappe

def execute():
    meta = frappe.get_meta("Sales Invoice")
    field = meta.get_field("naming_series")

    required_series = [
        "SI-.YY.-.####",
        "SR-.YY.-.####"
    ]

    current = field.options.split("\n") if field.options else []

    updated = False

    for series in required_series:
        if series not in current:
            current.append(series)
            updated = True

    if updated:
        frappe.db.set_value(
            "DocField",
            field.name,
            "options",
            "\n".join(current)
        )

        frappe.clear_cache(doctype="Sales Invoice")