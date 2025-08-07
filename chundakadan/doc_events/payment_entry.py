import frappe
from frappe import _

def set_custom_sales_person(doc, method):
    if doc.references:
        for ref in doc.references:
            if ref.reference_doctype and ref.reference_name:
                try:
                    ref_doc = frappe.get_doc(ref.reference_doctype, ref.reference_name)
                    if hasattr(ref_doc, "custom_sales_person") and ref_doc.custom_sales_person:
                        doc.custom_sales_person = ref_doc.custom_sales_person
                        break
                except Exception as e:
                    frappe.log_error(f"Error fetching custom_sales_person: {e}")

def validate_sales_person(doc, method):
    if not doc.is_new() and not doc.custom_sales_person:
        frappe.throw(_("The Sales Person is mandatory after saving the document. Please set it before submitting."))

