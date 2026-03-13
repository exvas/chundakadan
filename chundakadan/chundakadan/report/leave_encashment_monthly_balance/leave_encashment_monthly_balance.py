# Copyright (c) 2024, Chundakadan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, add_months, get_last_day
from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on

def execute(filters=None):
    if not filters:
        filters = {}
    
    columns = get_columns(filters)
    data = get_data(filters)
    chart = get_chart_data(data)
    summary = get_report_summary(data)
    
    return columns, data, None, chart, summary

def get_columns(filters):
    return [
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 120
        },
        {
            "label": _("Employee Name"),
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": _("Department"),
            "fieldname": "department",
            "fieldtype": "Link",
            "options": "Department",
            "width": 130
        },
        {
            "label": _("Leave Type"),
            "fieldname": "leave_type",
            "fieldtype": "Link",
            "options": "Leave Type",
            "width": 130
        },
        {
            "label": _("Encashment Enabled"),
            "fieldname": "encashment_enabled",
            "fieldtype": "Check",
            "width": 100
        },
        {
            "label": _("Total Eligible Leaves"),
            "fieldname": "total_eligible_leaves",
            "fieldtype": "Float",
            "width": 110,
            "precision": 2
        },
        {
            "label": _("Leaves Already Encashed"),
            "fieldname": "leaves_already_encashed",
            "fieldtype": "Float",
            "width": 120,
            "precision": 2
        },
        {
            "label": _("Leaves Taken"),
            "fieldname": "leaves_taken",
            "fieldtype": "Float",
            "width": 100,
            "precision": 2
        },
        {
            "label": _("Current Balance"),
            "fieldname": "current_balance",
            "fieldtype": "Float",
            "width": 110,
            "precision": 2
        },
        {
            "label": _("Pending for Encashment"),
            "fieldname": "pending_encashment_leaves",
            "fieldtype": "Float",
            "width": 130,
            "precision": 2
        },
        {
            "label": _("Basic Salary"),
            "fieldname": "basic_salary",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Payment Days"),
            "fieldname": "payment_days",
            "fieldtype": "Int",
            "width": 90
        },
        {
            "label": _("Per Day Rate"),
            "fieldname": "per_day_rate",
            "fieldtype": "Currency",
            "width": 110
        },
        {
            "label": _("Total Payable Amount"),
            "fieldname": "total_payable_amount",
            "fieldtype": "Currency",
            "width": 140
        }
    ]

def get_data(filters):
    company = filters.get("company")
    employee_id = filters.get("employee")
    leave_type_filter = filters.get("leave_type")
    payment_days = flt(filters.get("payment_days", 30))
    department = filters.get("department")

    if not employee_id:
        frappe.msgprint(_("Please select an Employee"))
        return []

    # Get employee details (joining and relieving date)
    employee_details = frappe.db.get_value("Employee", employee_id, ["date_of_joining", "relieving_date", "employee_name", "department", "company"], as_dict=True)
    if not employee_details:
        frappe.msgprint(_("Employee not found"))
        return []

    from_date = employee_details.date_of_joining
    relieving_date = employee_details.relieving_date

    if not from_date:
        frappe.msgprint(_("Employee Joining Date is missing"))
        return []

    # The calculation window should always end at the last day of the month 
    # BEFORE the reference/relieving date provided.
    ref_date = filters.get("to_date")
    if not ref_date:
        ref_date = relieving_date or frappe.utils.today()
    
    to_date = get_last_day(add_months(getdate(ref_date), -1))

    # Get Encashable Leave Types
    lt_filters = {"allow_encashment": 1}
    if leave_type_filter:
        lt_filters["name"] = leave_type_filter
        
    encashable_leave_types = frappe.get_all(
        "Leave Type", 
        filters=lt_filters, 
        fields=["name", "max_encashable_leaves", "non_encashable_leaves"]
    )
    encashable_lt_map = {lt.name: lt for lt in encashable_leave_types}
    
    if not encashable_lt_map:
        frappe.msgprint(_("No encashment-enabled leave types found"))
        return []

    # Fetch Leave Allocations for the employee in the joined period
    allocation_query = """
        SELECT 
            name, employee, employee_name, department, leave_type,
            total_leaves_allocated, total_leaves_encashed, from_date, to_date
        FROM `tabLeave Allocation`
        WHERE docstatus = 1
        AND employee = %(employee)s
        AND leave_type IN %(leave_types)s
        AND (from_date <= %(to_date)s AND to_date >= %(from_date)s)
    """
    
    allocations = frappe.db.sql(allocation_query, {
        "employee": employee_id,
        "leave_types": tuple(encashable_lt_map.keys()),
        "from_date": from_date,
        "to_date": to_date
    }, as_dict=True)

    if not allocations:
        # If no allocations found in the period, check if there are ANY allocations to avoid silent failure
        return []

    # Fetch Salary Structure Assignment
    salary_map = get_basic_salaries([employee_id])
    
    # Get leaves taken in the period
    leaves_taken_map = get_leaves_taken([employee_id], list(encashable_lt_map.keys()), from_date, to_date)

    data = []
    
    for alloc in allocations:
        lt_settings = encashable_lt_map.get(alloc.leave_type)
        basic_salary = flt(salary_map.get(alloc.employee, 0))
        
        # Prorate calculation (Month Based)
        # Calculation: (Allocated Leaves / Total Months in Allocation) * Months Worked (up to to_date)
        
        alloc_from = getdate(alloc.from_date)
        alloc_to = getdate(alloc.to_date)
        
        # Total months in the allocation period
        total_months = frappe.utils.month_diff(alloc_to, alloc_from)
        
        # Months elapsed until the end of previous month
        if to_date >= alloc_from:
            worked_months = frappe.utils.month_diff(to_date, alloc_from)
        else:
            worked_months = 0
            
        if total_months > 0:
            prorated_allocation = (flt(alloc.total_leaves_allocated) / total_months) * worked_months
        else:
            prorated_allocation = 0
            
        # Remove "pointed values" (decimals) as requested
        prorated_allocation = int(prorated_allocation)
        
        # Get leaves taken till to_date
        leaves_taken = flt(leaves_taken_map.get((alloc.employee, alloc.leave_type), 0))
        
        # Leaves already encashed from this allocation
        leaves_encashed = flt(alloc.total_leaves_encashed)
        
        # Calculate Balance on the calculated to_date (Prorated)
        # Current Balance = Prorated Allocation - Taken - Encashed
        balance = max(0, prorated_allocation - leaves_taken - leaves_encashed)
        
        # Calculate Pending Encashable Leaves
        max_encashable = flt(lt_settings.max_encashable_leaves) if lt_settings.max_encashable_leaves else 999999
        non_encashable = flt(lt_settings.non_encashable_leaves)
        
        encashable_balance = max(0, balance - non_encashable)
        pending_leaves = min(encashable_balance, max_encashable)
        
        # Calculate Amount
        per_day_rate = 0
        if payment_days > 0:
            per_day_rate = basic_salary / payment_days
            
        payable_amount = pending_leaves * per_day_rate
        
        row = {
            "employee": alloc.employee,
            "employee_name": alloc.employee_name,
            "department": alloc.department,
            "leave_type": alloc.leave_type,
            "company": employee_details.company or "",
            "encashment_enabled": 1,
            "total_eligible_leaves": prorated_allocation,
            "leaves_already_encashed": flt(alloc.total_leaves_encashed, 2),
            "leaves_taken": flt(leaves_taken, 2),
            "current_balance": flt(balance, 2),
            "pending_encashment_leaves": flt(pending_leaves, 2),
            "basic_salary": flt(basic_salary, 2),
            "payment_days": int(payment_days),
            "per_day_rate": flt(per_day_rate, 2),
            "total_payable_amount": flt(payable_amount, 2)
        }
        
        data.append(row)

    return data

def get_basic_salaries(employees):
    """Fetch the latest active salary structure assignment for each employee"""
    if not employees:
        return {}
    salary_map = {}
    assignments = frappe.db.sql("""
        SELECT employee, base
        FROM `tabSalary Structure Assignment`
        WHERE employee IN %(employees)s
        AND docstatus = 1
        ORDER BY from_date DESC
    """, {"employees": tuple(employees)}, as_dict=True)
    seen_employees = set()
    for assign in assignments:
        if assign.employee not in seen_employees:
            salary_map[assign.employee] = flt(assign.base)
            seen_employees.add(assign.employee)
    return salary_map

def get_leaves_taken(employees, leave_types, from_date, to_date):
    """Get total leaves taken by each employee for each leave type in the period"""
    if not employees or not leave_types:
        return {}
    leaves_taken = frappe.db.sql("""
        SELECT employee, leave_type, SUM(total_leave_days) as total_taken
        FROM `tabLeave Application`
        WHERE employee IN %(employees)s
        AND leave_type IN %(leave_types)s
        AND docstatus = 1
        AND status = 'Approved'
        AND from_date >= %(from_date)s
        AND to_date <= %(to_date)s
        GROUP BY employee, leave_type
    """, {
        "employees": tuple(employees),
        "leave_types": tuple(leave_types),
        "from_date": from_date,
        "to_date": to_date
    }, as_dict=True)
    leaves_map = {}
    for record in leaves_taken:
        leaves_map[(record.employee, record.leave_type)] = flt(record.total_taken)
    return leaves_map

def get_report_summary(data):
    if not data:
        return []
    total_employees = len(set(row["employee"] for row in data))
    total_pending_leaves = sum(flt(row["pending_encashment_leaves"]) for row in data)
    total_encashed_leaves = sum(flt(row["leaves_already_encashed"]) for row in data)
    total_payable = sum(flt(row["total_payable_amount"]) for row in data)
    return [
        {"value": total_employees, "label": _("Total Employees"), "datatype": "Int", "indicator": "blue"},
        {"value": total_pending_leaves, "label": _("Total Pending Leaves"), "datatype": "Float", "indicator": "orange"},
        {"value": total_encashed_leaves, "label": _("Total Encashed Leaves"), "datatype": "Float", "indicator": "green"},
        {"value": total_payable, "label": _("Total Payable Amount"), "datatype": "Currency", "indicator": "blue"}
    ]

def get_chart_data(data):
    if not data:
        return None
    leave_type_data = {}
    for row in data:
        lt = row["leave_type"]
        if lt not in leave_type_data:
            leave_type_data[lt] = {"pending": 0, "encashed": 0, "payable": 0}
        leave_type_data[lt]["pending"] += flt(row["pending_encashment_leaves"])
        leave_type_data[lt]["encashed"] += flt(row["leaves_already_encashed"])
        leave_type_data[lt]["payable"] += flt(row["total_payable_amount"])
    labels = list(leave_type_data.keys())
    pending_values = [leave_type_data[lt]["pending"] for lt in labels]
    encashed_values = [leave_type_data[lt]["encashed"] for lt in labels]
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("Pending for Encashment"), "values": pending_values},
                {"name": _("Already Encashed"), "values": encashed_values}
            ]
        },
        "type": "bar",
        "colors": ["#FFA500", "#28a745"]
    }

@frappe.whitelist()
def create_additional_salary(employee, leave_type, pending_leaves, amount, salary_component, 
                            payroll_date, overwrite_salary_structure_amount=1, company=None):
    from frappe.utils import getdate
    if not employee or not salary_component or not amount:
        frappe.throw(_("Employee, Salary Component, and Amount are required"))
    amount = flt(amount)
    pending_leaves = flt(pending_leaves)
    if amount <= 0: frappe.throw(_("Amount must be greater than zero"))
    if pending_leaves <= 0: frappe.throw(_("Pending leaves must be greater than zero"))
    employee_doc = frappe.get_doc("Employee", employee)
    if not company: company = employee_doc.company
    existing = frappe.db.exists("Additional Salary", {
        "employee": employee, "salary_component": salary_component, "payroll_date": getdate(payroll_date),
        "ref_doctype": "Leave Type", "ref_docname": leave_type, "docstatus": ["<", 2]
    })
    if existing: return existing
    additional_salary = frappe.get_doc({
        "doctype": "Additional Salary", "employee": employee, "employee_name": employee_doc.employee_name,
        "company": company, "salary_component": salary_component, "amount": amount,
        "payroll_date": getdate(payroll_date), "overwrite_salary_structure_amount": int(overwrite_salary_structure_amount),
        "ref_doctype": "Leave Type", "ref_docname": leave_type,
        "remarks": _("Monthly Leave Encashment: {0} leaves").format(pending_leaves)
    })
    additional_salary.insert()
    return additional_salary.name

@frappe.whitelist()
def bulk_create_additional_salary(employees_data, salary_component, payroll_date, 
                                  overwrite_salary_structure_amount=1):
    import json
    if isinstance(employees_data, str): employees_data = json.loads(employees_data)
    results = {"total": len(employees_data), "created": 0, "skipped": 0, "failed": 0, "errors": [], "created_docs": []}
    payroll_date = get_last_day(getdate(payroll_date))
    for emp_data in employees_data:
        try:
            employee = emp_data.get("employee")
            amount = flt(emp_data.get("amount", 0))
            if not employee or amount <= 0: continue
            employee_doc = frappe.get_doc("Employee", employee)
            existing = frappe.db.exists("Additional Salary", {
                "employee": employee, "salary_component": salary_component, "payroll_date": payroll_date,
                "ref_doctype": "Leave Type", "ref_docname": emp_data.get("leave_type"), "docstatus": ["<", 2]
            })
            if existing:
                results["skipped"] += 1
                continue
            additional_salary = frappe.get_doc({
                "doctype": "Additional Salary", "employee": employee, "employee_name": employee_doc.employee_name,
                "company": employee_doc.company, "salary_component": salary_component, "amount": amount,
                "payroll_date": payroll_date, "overwrite_salary_structure_amount": int(overwrite_salary_structure_amount),
                "ref_doctype": "Leave Type", "ref_docname": emp_data.get("leave_type"),
                "remarks": _("Monthly Leave Encashment: {0} leaves").format(emp_data.get("pending_leaves"))
            })
            additional_salary.insert()
            results["created"] += 1
            results["created_docs"].append(additional_salary.name)
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(str(e))
    frappe.db.commit()
    return results
