#!/usr/bin/env python3
"""
Helper script to check which employees need attendance_device_id mapping
Run: bench --site chundakadan.local execute chundakadan.check_employee_mapping.check_unmapped_employees
"""

import frappe

def check_unmapped_employees():
    """Check which employees don't have attendance_device_id set"""

    # Get all active employees
    employees = frappe.db.sql("""
        SELECT name, employee_name, attendance_device_id, status
        FROM `tabEmployee`
        WHERE status = 'Active'
        ORDER BY name
    """, as_dict=True)

    mapped_count = 0
    unmapped_count = 0

    print("\n" + "="*80)
    print("EMPLOYEE DEVICE ID MAPPING STATUS")
    print("="*80)

    print("\n✓ EMPLOYEES WITH DEVICE ID MAPPED:")
    print("-" * 80)
    for emp in employees:
        if emp.attendance_device_id:
            print(f"  {emp.name:20} | {emp.employee_name:40} | Device ID: {emp.attendance_device_id}")
            mapped_count += 1

    print(f"\nTotal: {mapped_count} employees")

    print("\n✗ EMPLOYEES WITHOUT DEVICE ID (Need Mapping):")
    print("-" * 80)
    for emp in employees:
        if not emp.attendance_device_id:
            print(f"  {emp.name:20} | {emp.employee_name:40}")
            unmapped_count += 1

    print(f"\nTotal: {unmapped_count} employees")

    print("\n" + "="*80)
    print(f"SUMMARY: {mapped_count} mapped, {unmapped_count} unmapped out of {len(employees)} total active employees")
    print("="*80 + "\n")

    if unmapped_count > 0:
        print("ACTION REQUIRED:")
        print("- Update the 'Attendance Device ID' field for each employee")
        print("- The Device ID should match the employee code used in CrossChex")
        print("- You can find CrossChex employee codes in the sync logs after running a sync\n")
