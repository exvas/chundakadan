#!/usr/bin/env python3
"""
Debug script to check what employee codes CrossChex is sending
and which employees don't have attendance_device_id mapped
"""

import frappe
from frappe.utils import now_datetime, get_datetime
from datetime import datetime, timedelta
import requests
import uuid
import json

def debug_crosschex_sync():
    frappe.init(site='chundakadan.local')
    frappe.connect()

    # Get CrossChex settings
    settings = frappe.get_single("Crosschex Settings")

    if not settings.api_configurations or len(settings.api_configurations) == 0:
        print("No API configurations found")
        return

    config = settings.api_configurations[0]  # Use first config

    print(f"\n=== Debugging CrossChex Sync for {config.configuration_name} ===\n")

    # Get token
    config_doc = frappe.get_doc("CrossChex API Configuration", config.name)
    api_secret = config_doc.get_password('api_secret')

    # Generate token
    api_url = config.api_url
    if not api_url.endswith('/'):
        api_url += '/'

    token_payload = {
        "header": {
            "nameSpace": "authorize.token",
            "nameAction": "token",
            "version": "1.0",
            "requestId": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
        },
        "payload": {
            "api_key": config.api_key,
            "api_secret": api_secret
        }
    }

    print("Getting access token...")
    response = requests.post(api_url, json=token_payload, headers={'Content-Type': 'application/json'}, timeout=30)

    if response.status_code != 200:
        print(f"Failed to get token: {response.status_code}")
        return

    token_data = response.json()
    if 'payload' not in token_data or 'token' not in token_data['payload']:
        print(f"Token error: {token_data}")
        return

    token = token_data['payload']['token']
    print("✓ Token obtained\n")

    # Fetch attendance records
    end_time = datetime.utcnow()
    begin_time = end_time - timedelta(hours=24)

    attendance_payload = {
        "header": {
            "nameSpace": "attendance.record",
            "nameAction": "getrecord",
            "version": "1.0",
            "requestId": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
        },
        "authorize": {
            "type": "token",
            "token": token
        },
        "payload": {
            "begin_time": begin_time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "end_time": end_time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "order": "asc",
            "page": 1,
            "per_page": 1000
        }
    }

    print("Fetching attendance records...")
    response = requests.post(api_url, json=attendance_payload, headers={'Content-Type': 'application/json'}, timeout=30)

    if response.status_code != 200:
        print(f"Failed to fetch attendance: {response.status_code}")
        return

    data = response.json()

    if 'payload' not in data or 'list' not in data['payload']:
        print("No attendance data in response")
        return

    records = data['payload']['list']
    print(f"✓ Found {len(records)} attendance records\n")

    if len(records) == 0:
        print("No records to process")
        return

    # Analyze employee codes
    print("=== CrossChex Employee Codes Found ===")
    emp_codes = set()
    for record in records:
        emp_code = record.get('emp_code')
        if emp_code:
            emp_codes.add(emp_code)

    print(f"Unique employee codes: {sorted(emp_codes)}")
    print(f"\nTotal unique employees: {len(emp_codes)}\n")

    # Check which employees exist in system
    print("=== Checking Employee Mappings ===")
    for emp_code in sorted(emp_codes):
        employee = frappe.db.get_value('Employee', {'attendance_device_id': emp_code}, ['name', 'employee_name'], as_dict=True)
        if employee:
            print(f"✓ {emp_code}: {employee.employee_name} ({employee.name})")
        else:
            print(f"✗ {emp_code}: NOT FOUND - No employee has attendance_device_id = '{emp_code}'")

    # Show sample records
    print(f"\n=== Sample Attendance Records (first 3) ===")
    for i, record in enumerate(records[:3], 1):
        print(f"\nRecord {i}:")
        print(f"  emp_code: {record.get('emp_code')}")
        print(f"  check_time: {record.get('check_time')}")
        print(f"  check_type: {record.get('check_type')}")
        print(f"  area_alias: {record.get('area_alias')}")
        print(f"  uuid: {record.get('uuid')}")

    # Check all employees with device IDs
    print("\n=== Employees with attendance_device_id in System ===")
    employees = frappe.db.sql("""
        SELECT name, employee_name, attendance_device_id
        FROM `tabEmployee`
        WHERE attendance_device_id IS NOT NULL AND attendance_device_id != ''
        ORDER BY attendance_device_id
    """, as_dict=True)

    print(f"Total: {len(employees)} employees")
    for emp in employees:
        print(f"  {emp.attendance_device_id}: {emp.employee_name} ({emp.name})")

    frappe.destroy()

if __name__ == "__main__":
    debug_crosschex_sync()
