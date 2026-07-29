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


CHECKIN_EDIT_ROLES = {"HR User", "HR Manager", "System Manager", "Administrator"}


@frappe.whitelist()
def update_checkin_time(checkin, new_time, reason):
    """HR-only path to correct an Employee Checkin's Time (the form itself is
    read-only). Logs the change and emails the configured recipients + the
    affected employee. Recomputes attendance so the corrected time takes
    effect in late-entry / attendance calculations.
    """
    from frappe.utils import get_datetime

    if not (CHECKIN_EDIT_ROLES & set(frappe.get_roles())):
        frappe.throw(frappe._("You are not permitted to update check-in time."))
    if not (reason or "").strip():
        frappe.throw(frappe._("A reason is required to update the check-in time."))
    if not new_time:
        frappe.throw(frappe._("New time is required."))

    doc = frappe.get_doc("Employee Checkin", checkin)
    old_time = doc.time
    new_dt = get_datetime(new_time)
    if get_datetime(old_time) == new_dt:
        frappe.throw(frappe._("New time is the same as the current time."))

    doc.time = new_dt
    doc.flags.ignore_permissions = True
    doc.save()

    doc.add_comment(
        "Info",
        frappe._("Check-in time changed from <b>{0}</b> to <b>{1}</b> by {2}.<br>Reason: {3}")
        .format(old_time, new_dt, frappe.session.user, frappe.utils.escape_html(reason.strip())),
    )
    # keep attendance in step with the corrected time
    try:
        mark_attendance(doc, "update_checkin_time")
    except Exception:
        frappe.log_error(title=f"mark_attendance after time update failed for {checkin}",
                         message=frappe.get_traceback())

    _notify_checkin_time_change(doc, old_time, new_dt, reason.strip())
    frappe.db.commit()
    return {"old": str(old_time), "new": str(new_dt)}


def _notify_checkin_time_change(doc, old_time, new_time, reason):
    """Email the Chundakadan Settings recipient list + the affected employee."""
    raw = frappe.db.get_single_value("Chundakadan Settings", "checkin_update_notification_emails") or ""
    recipients = []
    for chunk in raw.replace("\n", ",").replace(";", ",").split(","):
        addr = chunk.strip()
        if addr and addr not in recipients:
            recipients.append(addr)
    # affected employee
    emp_email = frappe.db.get_value("Employee", doc.employee,
                                    "company_email") or frappe.db.get_value(
                                        "Employee", doc.employee, "personal_email") or frappe.db.get_value(
                                        "Employee", doc.employee, "user_id")
    if emp_email and emp_email not in recipients:
        recipients.append(emp_email)
    if not recipients:
        return

    subject = frappe._("Check-in time updated: {0} ({1})").format(
        doc.employee_name or doc.employee, frappe.utils.formatdate(getdate(new_time)))
    message = frappe._(
        "<p>The check-in <b>{name}</b> for <b>{emp}</b> was updated.</p>"
        "<table cellpadding='6' style='border-collapse:collapse'>"
        "<tr><td><b>Employee</b></td><td>{emp} ({empid})</td></tr>"
        "<tr><td><b>Old time</b></td><td>{old}</td></tr>"
        "<tr><td><b>New time</b></td><td>{new}</td></tr>"
        "<tr><td><b>Changed by</b></td><td>{by}</td></tr>"
        "<tr><td><b>Reason</b></td><td>{reason}</td></tr></table>"
    ).format(
        name=doc.name, emp=doc.employee_name or doc.employee, empid=doc.employee,
        old=old_time, new=new_time, by=frappe.session.user,
        reason=frappe.utils.escape_html(reason),
    )
    frappe.sendmail(recipients=recipients, subject=subject, message=message,
                    reference_doctype="Employee Checkin", reference_name=doc.name)


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
