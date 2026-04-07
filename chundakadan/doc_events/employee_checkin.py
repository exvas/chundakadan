import frappe
from frappe.utils import getdate

def mark_attendance(doc, method):
    if not doc.employee or not doc.time:
        return
    
    date = getdate(doc.time)
    
    if doc.log_type != "IN":
        return
        
    status = "Present"
        
    attendance_name = frappe.db.get_value("Attendance", {
        "employee": doc.employee,
        "attendance_date": date,
        "docstatus": ("<", 2) # Not cancelled
    }, "name")
    
    if attendance_name:
        # Update existing attendance
        attendance = frappe.get_doc("Attendance", attendance_name)
        if attendance.status != status:
            if attendance.docstatus == 1:
                frappe.db.set_value("Attendance", attendance_name, "status", status)
            else:
                attendance.db_set("status", status)
    else:
        # Create new attendance
        company = frappe.db.get_value("Employee", doc.employee, "company")
        attendance = frappe.get_doc({
            "doctype": "Attendance",
            "employee": doc.employee,
            "attendance_date": date,
            "status": status,
            "company": company
        })
        attendance.flags.ignore_validate = True
        attendance.insert(ignore_permissions=True)
        if hasattr(attendance, "submit") and getattr(attendance.meta, "is_submittable", False):
            attendance.submit()
