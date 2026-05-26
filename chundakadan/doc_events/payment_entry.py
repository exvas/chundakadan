import frappe

def set_custom_sales_person(doc, method=None):

    if doc.custom_sales_persons:
        return

    if not doc.references:
        return

    for ref in doc.references:

        if (
            ref.reference_doctype == "Sales Invoice"
            and ref.reference_name
        ):

            sales_person = frappe.db.get_value(
                "Sales Invoice",
                ref.reference_name,
                "custom_sales_person"
            )

            if sales_person:
                doc.custom_sales_persons = sales_person
                return


def validate_check_bounce(doc, method=None):

    if doc.custom_check_bounce:
        frappe.throw(
            "Cannot submit Payment Entry because cheque bounce is checked."
        )