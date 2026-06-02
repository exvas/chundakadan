# Copyright (c) 2026, Chundakadan
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("From Date and To Date are required"))

    swh = (
        frappe.db.get_single_value("HR Settings", "standard_working_hours") or 0
    )
    columns = get_columns()
    data = get_data(filters, swh)
    return columns, data


def get_columns():
    return [
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 120,
        },
        {
            "label": _("Employee Name"),
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": _("Date"),
            "fieldname": "att_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": _("First In Time"),
            "fieldname": "first_in",
            "fieldtype": "Time",
            "width": 110,
        },
        {
            "label": _("Last Out Time"),
            "fieldname": "last_out",
            "fieldtype": "Time",
            "width": 110,
        },
        {
            "label": _("SWH (hrs)"),
            "fieldname": "swh",
            "fieldtype": "Float",
            "precision": 2,
            "width": 90,
        },
        {
            "label": _("Total Time (hrs)"),
            "fieldname": "total_time",
            "fieldtype": "Float",
            "precision": 2,
            "width": 120,
        },
        {
            "label": _("Over Time (hrs)"),
            "fieldname": "over_time",
            "fieldtype": "Float",
            "precision": 2,
            "width": 120,
        },
    ]


def get_data(filters, swh):
    # Aggregate per (employee, date) — earliest IN, latest OUT
    where = ["DATE(c.time) BETWEEN %(from_date)s AND %(to_date)s"]
    params = {
        "from_date": filters.from_date,
        "to_date": filters.to_date,
    }
    if filters.get("employee"):
        where.append("c.employee = %(employee)s")
        params["employee"] = filters.employee
    if filters.get("company"):
        where.append("e.company = %(company)s")
        params["company"] = filters.company

    rows = frappe.db.sql(
        f"""
        SELECT
            c.employee                                           AS employee,
            COALESCE(e.employee_name, c.employee)                AS employee_name,
            DATE(c.time)                                         AS att_date,
            MIN(CASE WHEN c.log_type = 'IN'  THEN c.time END)    AS first_in_dt,
            MAX(CASE WHEN c.log_type = 'OUT' THEN c.time END)    AS last_out_dt
        FROM `tabEmployee Checkin` c
        LEFT JOIN `tabEmployee` e ON e.name = c.employee
        WHERE {' AND '.join(where)}
        GROUP BY c.employee, DATE(c.time)
        ORDER BY c.employee, att_date
        """,
        params,
        as_dict=True,
    )

    output = []
    for r in rows:
        first_in_dt = r.get("first_in_dt")
        last_out_dt = r.get("last_out_dt")
        # Frappe returns datetime objects from DATETIME columns. Time
        # column on the report expects timedelta or string.
        first_in = _time_part(first_in_dt)
        last_out = _time_part(last_out_dt)

        total_time = None
        over_time = None
        if first_in_dt and last_out_dt and last_out_dt > first_in_dt:
            total_seconds = (last_out_dt - first_in_dt).total_seconds()
            total_time = round(total_seconds / 3600.0, 2)
            over_time = round(max(0.0, total_time - (swh or 0)), 2)

        output.append({
            "employee": r["employee"],
            "employee_name": r["employee_name"],
            "att_date": r["att_date"],
            "first_in": first_in,
            "last_out": last_out,
            "swh": swh,
            "total_time": total_time,
            "over_time": over_time,
        })

    return output


def _time_part(dt):
    """Return a `datetime.timedelta` representing the time-of-day, which
    is how Frappe's Time fieldtype renders cleanly in reports/Excel.
    None passes through.
    """
    if not dt:
        return None
    import datetime
    return datetime.timedelta(
        hours=dt.hour, minutes=dt.minute, seconds=dt.second,
    )
