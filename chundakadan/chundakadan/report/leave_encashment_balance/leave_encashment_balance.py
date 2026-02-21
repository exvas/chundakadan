# Copyright (c) 2024, Chundakadan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
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
    leave_period = filters.get("leave_period")
    department = filters.get("department")
    employee = filters.get("employee")
    leave_type = filters.get("leave_type")
    payment_days = flt(filters.get("payment_days", 30))
    
    # Get company from leave period if not provided
    if not company and leave_period:
        company = frappe.db.get_value("Leave Period", leave_period, "company")

    if not leave_period:
        frappe.msgprint(_("Please select Leave Period"))
        return []

    # Get Leave Period details
    lp_details = frappe.db.get_value("Leave Period", leave_period, ["from_date", "to_date"], as_dict=True)
    if not lp_details:
        frappe.msgprint(_("Invalid Leave Period"))
        return []
    
    to_date = lp_details.to_date

    # Get Encashable Leave Types
    lt_filters = {"allow_encashment": 1}
    if leave_type:
        lt_filters["name"] = leave_type
        
    encashable_leave_types = frappe.get_all(
        "Leave Type", 
        filters=lt_filters, 
        fields=["name", "max_encashable_leaves", "non_encashable_leaves"]
    )
    encashable_lt_map = {lt.name: lt for lt in encashable_leave_types}
    
    if not encashable_lt_map:
        frappe.msgprint(_("No encashment-enabled leave types found"))
        return []

    # Build Filter Conditions for Leave Allocation
    conditions = {"leave_period": leave_period, "leave_type": ["in", list(encashable_lt_map.keys())]}
    if employee:
        conditions["employee"] = employee
    if department:
        conditions["department"] = department
    if company:
        conditions["company"] = company

    # Fetch Leave Allocations
    allocations = frappe.get_all(
        "Leave Allocation",
        filters=conditions,
        fields=[
            "employee", "employee_name", "department", "leave_type",
            "total_leaves_allocated", "total_leaves_encashed"
        ]
    )

    if not allocations:
        frappe.msgprint(_("No leave allocations found for the selected criteria"))
        return []

    # Fetch Salary Structure Assignments
    employees = [d.employee for d in allocations]
    salary_map = get_basic_salaries(employees)
    
    # Get leaves taken for each employee and leave type
    leaves_taken_map = get_leaves_taken(employees, list(encashable_lt_map.keys()), lp_details.from_date, to_date)

    data = []
    
    for alloc in allocations:
        lt_settings = encashable_lt_map.get(alloc.leave_type)
        basic_salary = flt(salary_map.get(alloc.employee, 0))
        
        # Calculate Balance
        balance = flt(get_leave_balance_on(alloc.employee, alloc.leave_type, to_date))
        
        # Get leaves taken
        leaves_taken = flt(leaves_taken_map.get((alloc.employee, alloc.leave_type), 0))
        
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
            "company": company or "",
            "encashment_enabled": 1,
            "total_eligible_leaves": flt(alloc.total_leaves_allocated, 2),
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
    
    # Get the latest assignment for each employee
    assignments = frappe.db.sql("""
        SELECT employee, base
        FROM `tabSalary Structure Assignment`
        WHERE employee IN %(employees)s
        AND docstatus = 1
        ORDER BY from_date DESC
    """, {"employees": tuple(employees)}, as_dict=True)
    
    # Since we ordered by from_date DESC, the first occurrence is the latest
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
    """Generate summary cards for the report"""
    if not data:
        return []
    
    total_employees = len(set(row["employee"] for row in data))
    total_pending_leaves = sum(flt(row["pending_encashment_leaves"]) for row in data)
    total_encashed_leaves = sum(flt(row["leaves_already_encashed"]) for row in data)
    total_payable = sum(flt(row["total_payable_amount"]) for row in data)
    
    return [
        {
            "value": total_employees,
            "label": _("Total Employees"),
            "datatype": "Int",
            "indicator": "blue"
        },
        {
            "value": total_pending_leaves,
            "label": _("Total Pending Leaves"),
            "datatype": "Float",
            "indicator": "orange"
        },
        {
            "value": total_encashed_leaves,
            "label": _("Total Encashed Leaves"),
            "datatype": "Float",
            "indicator": "green"
        },
        {
            "value": total_payable,
            "label": _("Total Payable Amount"),
            "datatype": "Currency",
            "indicator": "blue"
        }
    ]

def get_chart_data(data):
    """Generate chart data for visualization"""
    if not data:
        return None
    
    # Group by leave type
    leave_type_data = {}
    for row in data:
        lt = row["leave_type"]
        if lt not in leave_type_data:
            leave_type_data[lt] = {
                "pending": 0,
                "encashed": 0,
                "payable": 0
            }
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
                {
                    "name": _("Pending for Encashment"),
                    "values": pending_values
                },
                {
                    "name": _("Already Encashed"),
                    "values": encashed_values
                }
            ]
        },
        "type": "bar",
        "colors": ["#FFA500", "#28a745"]
    }


@frappe.whitelist()
def create_additional_salary(employee, leave_type, pending_leaves, amount, salary_component, 
                            payroll_date, overwrite_salary_structure_amount=1, company=None):
    """
    Create Additional Salary entry for leave encashment
    
    Args:
        employee: Employee ID
        leave_type: Leave Type name
        pending_leaves: Number of leaves to encash
        amount: Total payable amount
        salary_component: Salary Component for leave encashment
        payroll_date: Date for payroll processing
        overwrite_salary_structure_amount: Whether to overwrite salary structure amount
        company: Company name
    
    Returns:
        Name of created Additional Salary document
    """
    from frappe.utils import getdate, nowdate
    
    # Validate inputs
    if not employee or not salary_component or not amount:
        frappe.throw(_("Employee, Salary Component, and Amount are required"))
    
    amount = flt(amount)
    pending_leaves = flt(pending_leaves)
    
    if amount <= 0:
        frappe.throw(_("Amount must be greater than zero"))
    
    if pending_leaves <= 0:
        frappe.throw(_("Pending leaves must be greater than zero"))
    
    # Get employee details
    employee_doc = frappe.get_doc("Employee", employee)
    
    if not company:
        company = employee_doc.company
    
    # Check if Additional Salary already exists for this employee, leave type, and payroll date
    existing = frappe.db.exists("Additional Salary", {
        "employee": employee,
        "salary_component": salary_component,
        "payroll_date": getdate(payroll_date),
        "docstatus": ["<", 2]  # Not cancelled
    })
    
    if existing:
        frappe.msgprint(
            _("Additional Salary {0} already exists for this employee and payroll date. Please check and update if needed.").format(
                '<a href="/app/additional-salary/{0}">{0}</a>'.format(existing)
            ),
            indicator="orange",
            alert=True
        )
        return existing
    
    # Create Additional Salary document
    additional_salary = frappe.get_doc({
        "doctype": "Additional Salary",
        "employee": employee,
        "employee_name": employee_doc.employee_name,
        "company": company,
        "salary_component": salary_component,
        "amount": amount,
        "payroll_date": getdate(payroll_date),
        "overwrite_salary_structure_amount": int(overwrite_salary_structure_amount),
        "ref_doctype": "Leave Type",
        "ref_docname": leave_type,
        "remarks": _("Leave Encashment for {0} - {1} leaves @ {2} per day").format(
            leave_type,
            pending_leaves,
            flt(amount / pending_leaves, 2) if pending_leaves > 0 else 0
        )
    })
    
    additional_salary.insert(ignore_permissions=False)
    
    frappe.msgprint(
        _("Additional Salary {0} created successfully").format(
            '<a href="/app/additional-salary/{0}">{0}</a>'.format(additional_salary.name)
        ),
        indicator="green",
        alert=True
    )
    
    return additional_salary.name


@frappe.whitelist()
def bulk_create_additional_salary(employees_data, salary_component, payroll_date, 
                                  overwrite_salary_structure_amount=1):
    """
    Bulk create Additional Salary entries for multiple employees
    
    Args:
        employees_data: List of employee dictionaries with employee, leave_type, pending_leaves, amount, company
        salary_component: Salary Component for leave encashment
        payroll_date: Date for payroll processing
        overwrite_salary_structure_amount: Whether to overwrite salary structure amount
    
    Returns:
        Dictionary with creation results
    """
    import json
    from frappe.utils import getdate
    
    # Parse employees_data if it's a string
    if isinstance(employees_data, str):
        employees_data = json.loads(employees_data)
    
    results = {
        "total": len(employees_data),
        "created": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
        "created_docs": []
    }
    
    payroll_date = getdate(payroll_date)
    
    # Log the incoming data for debugging
    frappe.log_error(
        title="Bulk Additional Salary - Input Data",
        message=f"Employees: {len(employees_data)}\nSalary Component: {salary_component}\nPayroll Date: {payroll_date}\nData: {json.dumps(employees_data, indent=2)}"
    )
    
    for emp_data in employees_data:
        employee = None
        employee_name = None
        
        try:
            employee = emp_data.get("employee")
            employee_name = emp_data.get("employee_name", employee)
            leave_type = emp_data.get("leave_type")
            pending_leaves = flt(emp_data.get("pending_leaves", 0))
            amount = flt(emp_data.get("amount", 0))
            company = emp_data.get("company") or ""
            
            # Validate employee ID
            if not employee:
                results["failed"] += 1
                results["errors"].append(f"Missing employee ID in data")
                continue
            
            # Validate amount
            if not amount or amount <= 0:
                results["failed"] += 1
                results["errors"].append(f"{employee_name} ({employee}): Invalid amount ({amount})")
                continue
            
            # Get and validate employee details
            try:
                if not frappe.db.exists("Employee", employee):
                    results["failed"] += 1
                    results["errors"].append(f"{employee}: Employee record not found in database")
                    continue
                    
                employee_doc = frappe.get_doc("Employee", employee)
                employee_name = employee_doc.employee_name
                
                # Ensure company is set
                if not company:
                    company = employee_doc.company
                    
                if not company:
                    results["failed"] += 1
                    results["errors"].append(f"{employee_name} ({employee}): No company found")
                    continue
                    
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"{employee}: Error fetching employee - {str(e)}")
                frappe.log_error(
                    title=f"Employee Fetch Error - {employee}",
                    message=f"Error: {str(e)}\nEmployee: {employee}\nData: {json.dumps(emp_data, indent=2)}"
                )
                continue
            
            # Check if Additional Salary already exists
            existing = frappe.db.exists("Additional Salary", {
                "employee": employee,
                "salary_component": salary_component,
                "payroll_date": payroll_date,
                "docstatus": ["<", 2]  # Not cancelled
            })
            
            if existing:
                results["skipped"] += 1
                continue
            
            # Create Additional Salary document
            try:
                additional_salary = frappe.get_doc({
                    "doctype": "Additional Salary",
                    "employee": employee,
                    "employee_name": employee_name,
                    "company": company,
                    "salary_component": salary_component,
                    "amount": amount,
                    "payroll_date": payroll_date,
                    "overwrite_salary_structure_amount": int(overwrite_salary_structure_amount),
                    "ref_doctype": "Leave Type",
                    "ref_docname": leave_type,
                    "remarks": _("Leave Encashment for {0} - {1} leaves @ {2} per day").format(
                        leave_type,
                        pending_leaves,
                        flt(amount / pending_leaves, 2) if pending_leaves > 0 else 0
                    )
                })
                
                # Insert with permissions check
                additional_salary.insert()
                
                results["created"] += 1
                results["created_docs"].append(additional_salary.name)
                
            except Exception as e:
                results["failed"] += 1
                error_msg = f"{employee_name} ({employee}): {str(e)}"
                results["errors"].append(error_msg)
                frappe.log_error(
                    title=f"Additional Salary Creation Error - {employee}",
                    message=f"Employee: {employee}\nEmployee Name: {employee_name}\nCompany: {company}\nAmount: {amount}\nError: {str(e)}\nFull Data: {json.dumps(emp_data, indent=2)}"
                )
            
        except Exception as e:
            results["failed"] += 1
            error_msg = f"{employee_name or employee or 'Unknown'}: {str(e)}"
            results["errors"].append(error_msg)
            frappe.log_error(
                title=f"Bulk Additional Salary - Unexpected Error",
                message=f"Employee: {employee}\nError: {error_msg}\nData: {json.dumps(emp_data, indent=2)}"
            )
    
    # Commit the transaction
    frappe.db.commit()
    
    # Log the results
    frappe.log_error(
        title="Bulk Additional Salary - Results",
        message=f"Total: {results['total']}\nCreated: {results['created']}\nSkipped: {results['skipped']}\nFailed: {results['failed']}\nErrors: {json.dumps(results['errors'], indent=2)}"
    )
    
    return results
