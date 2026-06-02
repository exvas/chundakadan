import frappe
from frappe.utils import getdate


def resolve_location(doc, method=None):
    """Reverse-geocode the checkin's lat/long and store the human-readable
    address in `custom_location`. Runs as after_insert. Skips if:
      - no coordinates
      - custom_location field doesn't exist on the doctype (Custom Field
        wasn't created yet)
      - custom_location is already populated (idempotent on re-runs)

    Uses OpenStreetMap Nominatim — free, no API key. Rate limit is 1
    req/sec; we enqueue to the long queue so a burst of checkins doesn't
    block the user's save and only hits the API in the background.
    """
    if not (doc.latitude and doc.longitude):
        return
    # Custom Field check — skip silently if the field hasn't been created
    if not doc.meta.has_field("custom_location"):
        return
    if doc.get("custom_location"):
        return
    frappe.enqueue(
        "chundakadan.doc_events.employee_checkin._geocode_and_save",
        queue="long",
        timeout=120,
        job_name=f"geocode_{doc.name}",
        checkin=doc.name,
        lat=str(doc.latitude),
        lon=str(doc.longitude),
    )


def _geocode_and_save(checkin, lat, lon):
    """Background job. Calls Nominatim, writes the result to
    custom_location via db.set_value (Employee Checkin is submittable
    but custom_location has no GL impact).
    """
    import requests

    try:
        res = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 18, "addressdetails": 1},
            headers={"User-Agent": "chundakadan-erp/1.0 (contact: sammish.thundiyil@gmail.com)"},
            timeout=15,
        )
        if res.status_code != 200:
            return
        data = res.json()
        # display_name is the comma-separated full address; trim to first
        # ~250 chars so it fits a Small Text field without overflow.
        address = (data.get("display_name") or "").strip()
        if not address:
            return
        if len(address) > 250:
            address = address[:247] + "…"
        frappe.db.set_value(
            "Employee Checkin", checkin, "custom_location", address,
            update_modified=False,
        )
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "employee_checkin._geocode_and_save")


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
