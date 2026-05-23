import frappe


def execute():
    """
    Fix: The old 'add_sales_invoice_naming_series' patch wrote directly to
    tabDocField which gets reset on every bench migrate when ERPNext resyncs
    its core fixtures. Property Setters are the correct approach as they
    persist across migrations.
    """
    new_series = [
        "SI-.YY.-.####",
        "SR-.YY.-.####",
    ]

    # ---- options property setter ----
    ps_options = "Sales Invoice-naming_series-options"

    if frappe.db.exists("Property Setter", ps_options):
        ps = frappe.get_doc("Property Setter", ps_options)
        current = [s for s in (ps.value or "").split("\n") if s]
        changed = False
        for s in new_series:
            if s not in current:
                current.append(s)
                changed = True
        if changed:
            ps.value = "\n".join(current)
            ps.save(ignore_permissions=True)
    else:
        meta = frappe.get_meta("Sales Invoice")
        field = meta.get_field("naming_series")
        base = [s for s in (field.options or "").split("\n") if s]
        all_options = base + [s for s in new_series if s not in base]
        frappe.get_doc({
            "doctype": "Property Setter",
            "name": ps_options,
            "doctype_or_field": "DocField",
            "doc_type": "Sales Invoice",
            "field_name": "naming_series",
            "property": "options",
            "property_type": "Text",
            "value": "\n".join(all_options),
            "module": "Chundakadan",
        }).insert(ignore_permissions=True)

    # ---- default property setter ----
    ps_default = "Sales Invoice-naming_series-default"

    if frappe.db.exists("Property Setter", ps_default):
        ps = frappe.get_doc("Property Setter", ps_default)
        if ps.value != "SI-.YY.-.####":
            ps.value = "SI-.YY.-.####"
            ps.save(ignore_permissions=True)
    else:
        frappe.get_doc({
            "doctype": "Property Setter",
            "name": ps_default,
            "doctype_or_field": "DocField",
            "doc_type": "Sales Invoice",
            "field_name": "naming_series",
            "property": "default",
            "property_type": "Text",
            "value": "SI-.YY.-.####",
            "module": "Chundakadan",
        }).insert(ignore_permissions=True)

    frappe.clear_cache()
