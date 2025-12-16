import frappe
import requests
import uuid
from datetime import datetime, timedelta

@frappe.whitelist()
def diagnose():
    """Diagnose CrossChex sync issues"""

    # Get config
    config = frappe.db.get_value('CrossChex API Configuration',
                                  {'configuration_name': 'HOD'},
                                  ['name', 'api_url', 'api_key'],
                                  as_dict=True)

    if not config:
        print("ERROR: HOD configuration not found")
        return

    # Get API secret
    config_doc = frappe.get_doc("CrossChex API Configuration", config.name)
    api_secret = config_doc.get_password('api_secret')
    api_url = config.api_url.rstrip('/') + '/'

    print("="*80)
    print("CROSSCHEX SYNC DIAGNOSTIC")
    print("="*80)
    print(f"\nConfiguration: {config_doc.configuration_name}")
    print(f"API URL: {api_url}")
    print(f"API Key: {config.api_key}")

    # Step 1: Get Token
    print("\n[Step 1] Getting access token...")
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

    try:
        response = requests.post(api_url, json=token_payload,
                                headers={'Content-Type': 'application/json'}, timeout=30)

        if response.status_code != 200:
            print(f"ERROR: Failed to get token - HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return

        token_data = response.json()
        if 'payload' not in token_data or 'token' not in token_data['payload']:
            print(f"ERROR: Invalid token response")
            print(f"Response: {token_data}")
            return

        token = token_data['payload']['token']
        print("✓ Token obtained successfully")

    except Exception as e:
        print(f"ERROR: Exception getting token - {str(e)}")
        return

    # Step 2: Fetch Attendance Records
    print("\n[Step 2] Fetching attendance records...")

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

    try:
        response = requests.post(api_url, json=attendance_payload,
                                headers={'Content-Type': 'application/json'}, timeout=30)

        if response.status_code != 200:
            print(f"ERROR: Failed to fetch attendance - HTTP {response.status_code}")
            return

        data = response.json()

        if 'payload' not in data or 'list' not in data['payload']:
            print("ERROR: No attendance data in response")
            print(f"Response: {data}")
            return

        records = data['payload']['list']
        print(f"✓ Found {len(records)} attendance records")

    except Exception as e:
        print(f"ERROR: Exception fetching attendance - {str(e)}")
        return

    if len(records) == 0:
        print("\nNo records found in the last 24 hours")
        return

    # Step 3: Analyze Employee Codes
    print("\n[Step 3] Analyzing employee codes...")

    emp_codes = {}
    for record in records:
        emp_code = record.get('emp_code')
        if emp_code:
            if emp_code not in emp_codes:
                emp_codes[emp_code] = 0
            emp_codes[emp_code] += 1

    print(f"\nFound {len(emp_codes)} unique employee codes:")
    print("-" * 80)

    for emp_code in sorted(emp_codes.keys()):
        count = emp_codes[emp_code]

        # Check if employee exists
        employee = frappe.db.get_value('Employee',
                                       {'attendance_device_id': emp_code},
                                       ['name', 'employee_name'],
                                       as_dict=True)

        if employee:
            print(f"  ✓ Device ID '{emp_code}': {employee.employee_name} ({employee.name}) - {count} records")
        else:
            print(f"  ✗ Device ID '{emp_code}': NO EMPLOYEE MAPPED - {count} records")

    # Step 4: Show sample records
    print(f"\n[Step 4] Sample Records (first 5):")
    print("-" * 80)

    for i, record in enumerate(records[:5], 1):
        print(f"\nRecord {i}:")
        print(f"  emp_code: {record.get('emp_code')}")
        print(f"  emp_name: {record.get('emp_fname', '')} {record.get('emp_lname', '')}")
        print(f"  check_time: {record.get('check_time')}")
        print(f"  check_type: {record.get('check_type')}")
        print(f"  area_alias: {record.get('area_alias')}")
        print(f"  uuid: {record.get('uuid')}")

    # Step 5: Check existing check-ins
    print(f"\n[Step 5] Checking existing Employee Checkins from CrossChex...")

    existing = frappe.db.sql("""
        SELECT COUNT(*) as count
        FROM `tabEmployee Checkin`
        WHERE custom_crosschex_uuid IS NOT NULL
    """, as_dict=True)

    print(f"Existing CrossChex check-ins in system: {existing[0].count}")

    # Step 6: Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total records from CrossChex: {len(records)}")
    print(f"Unique employees: {len(emp_codes)}")

    mapped = sum(1 for code in emp_codes if frappe.db.exists('Employee', {'attendance_device_id': code}))
    unmapped = len(emp_codes) - mapped

    print(f"Employees mapped: {mapped}")
    print(f"Employees NOT mapped: {unmapped}")

    if unmapped > 0:
        print(f"\n⚠️  ACTION REQUIRED:")
        print(f"   {unmapped} employee(s) don't have attendance_device_id set")
        print(f"   Update the 'Attendance Device ID' field for these employees")
    else:
        print(f"\n✓ All employees are mapped!")
        print(f"  If sync is still showing 0 records, check:")
        print(f"  - All records might be duplicates (already synced)")
        print(f"  - Check frappe.log for detailed errors")

    print("="*80)
