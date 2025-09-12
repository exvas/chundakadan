# Copyright (c) 2025, Ashkar and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {"label": "Customer Name", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 200},
        {"label": "District", "fieldname": "district", "fieldtype": "Data", "width": 120},
        {"label": "Sales Executive", "fieldname": "sales_executive", "fieldtype": "Data", "width": 150},
        {"label": "January", "fieldname": "jan", "fieldtype": "Currency", "width": 100},
        {"label": "February", "fieldname": "feb", "fieldtype": "Currency", "width": 100},
        {"label": "March", "fieldname": "mar", "fieldtype": "Currency", "width": 100},
        {"label": "April", "fieldname": "apr", "fieldtype": "Currency", "width": 100},
        {"label": "May", "fieldname": "may", "fieldtype": "Currency", "width": 100},
        {"label": "June", "fieldname": "jun", "fieldtype": "Currency", "width": 100},
        {"label": "July", "fieldname": "jul", "fieldtype": "Currency", "width": 100},
        {"label": "August", "fieldname": "aug", "fieldtype": "Currency", "width": 100},
        {"label": "September", "fieldname": "sep", "fieldtype": "Currency", "width": 100},
        {"label": "October", "fieldname": "oct", "fieldtype": "Currency", "width": 100},
        {"label": "November", "fieldname": "nov", "fieldtype": "Currency", "width": 100},
        {"label": "December", "fieldname": "dec", "fieldtype": "Currency", "width": 100},
        {"label": "YTD Total", "fieldname": "total", "fieldtype": "Currency", "width": 120},
        {"label": "YTD Average", "fieldname": "ytd_avg", "fieldtype": "Currency", "width": 120},
        {"label": "Last 3 Months Average", "fieldname": "last_3_avg", "fieldtype": "Currency", "width": 150},
        {"label": "Category", "fieldname": "category", "fieldtype": "Data", "width": 120},
        {"label": "Remarks", "fieldname": "remarks", "fieldtype": "Data", "width": 150},
        {"label": "Notes", "fieldname": "notes", "fieldtype": "Data", "width": 150},
    ]


def get_conditions(filters):
    conditions = ["si.docstatus = 1"]

    if filters.get("year"):
        conditions.append("YEAR(si.posting_date) = %(year)s")
    if filters.get("customer"):
        conditions.append("si.customer = %(customer)s")
    if filters.get("district"):
        conditions.append("c.territory = %(district)s")
    if filters.get("sales_executive"):
        conditions.append("si.custom_sales_person = %(sales_executive)s")

    return " AND ".join(conditions)


def get_data(filters):
    conditions = get_conditions(filters)

    invoices = frappe.db.sql(f"""
        SELECT
            si.customer,
            c.territory as district,
            si.custom_sales_person as sales_executive,
            MONTH(si.posting_date) as month,
            SUM(sii.base_net_amount) as amount
        FROM `tabSales Invoice` si
        JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        JOIN `tabCustomer` c ON c.name = si.customer
        WHERE {conditions}
        GROUP BY si.customer, c.territory, si.custom_sales_person, MONTH(si.posting_date)
    """, filters, as_dict=True)

    data_map = {}
    for inv in invoices:
        key = (inv.customer, inv.district, inv.sales_executive)
        if key not in data_map:
            data_map[key] = {
                "customer": inv.customer,
                "district": inv.district,
                "sales_executive": inv.sales_executive,
                "jan": 0, "feb": 0, "mar": 0, "apr": 0,
                "may": 0, "jun": 0, "jul": 0, "aug": 0,
                "sep": 0, "oct": 0, "nov": 0, "dec": 0,
                "total": 0, "ytd_avg": 0, "last_3_avg": 0,
                "category": "", "remarks": "", "notes": ""
            }

        month_map = {
            1: "jan", 2: "feb", 3: "mar", 4: "apr",
            5: "may", 6: "jun", 7: "jul", 8: "aug",
            9: "sep", 10: "oct", 11: "nov", 12: "dec"
        }

        month_key = month_map.get(inv.month)
        if month_key:
            data_map[key][month_key] += inv.amount
            data_map[key]["total"] += inv.amount

    results = []
    sl_no = 1
    for k, row in data_map.items():
        row["ytd_avg"] = row["total"] / 12 if row["total"] else 0

        last_3_months = [row["oct"], row["nov"], row["dec"]]
        valid_months = [m for m in last_3_months if m > 0]
        row["last_3_avg"] = sum(valid_months) / len(valid_months) if valid_months else 0

        row["sl_no"] = sl_no
        sl_no += 1

        results.append(row)

    return results
