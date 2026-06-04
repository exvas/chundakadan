import frappe
from frappe.utils import getdate

from chundakadan.utils.geocode import resolve_for_doc


def resolve_location(doc, method=None):
    """Reverse-geocode the checkin's lat/long → custom_location.
    Employee Checkin's GPS fields are `latitude` / `longitude`; this
    delegates to the shared util in chundakadan.utils.geocode.
    """
    resolve_for_doc(doc)


# Kept as a compat shim — Frappe queues older RQ jobs that reference
# the old import path (chundakadan.doc_events.employee_checkin._geocode_and_save).
# Re-routes to the shared util. Safe to remove once the long queue
# fully drains of in-flight pre-refactor jobs.
def _geocode_and_save(checkin, lat, lon):
    from chundakadan.utils.geocode import _geocode_and_save as _new
    return _new("Employee Checkin", checkin, lat, lon)


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
