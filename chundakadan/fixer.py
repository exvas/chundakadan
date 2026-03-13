import frappe  # type: ignore

def run():
    child_tables = [
        "Employee Details", 
        "Earnings Breakdown", 
        "Deductions", 
        "Net Settlement Amount", 
        "HR Approval"
    ]

    for doctype in child_tables:
        doc = frappe.get_doc("DocType", doctype)
        dirty = False
        
        list_view_fields = [f.fieldname for f in doc.fields if f.in_list_view]
        
        for field in doc.fields:
            if field.fieldtype not in ["Section Break", "Column Break", "HTML", "Tab Break"]:
                if not field.in_list_view and len(list_view_fields) < 4:
                    field.in_list_view = 1
                    list_view_fields.append(field.fieldname)
                    dirty = True
            
            if field.fieldname in ["details", "properties", "description", "component", "descriptionformula", "entries", "role", "no", "name_and_signature", "date"]:
                if not field.read_only:
                    field.read_only = 1
                    dirty = True
        
        if dirty:
            try:
                doc.save(ignore_permissions=True)
                print(f"Updated {doctype}")
            except Exception as e:
                print(f"Error updating {doctype}: {e}")
            
    frappe.db.commit()
