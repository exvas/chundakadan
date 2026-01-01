# Copyright (c) 2025, Chundakadan and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime
import requests
import json
from datetime import datetime, timedelta


class CrosschexSettings(Document):
    def validate(self):
        """Validate CrossChex Settings before saving"""
        if self.enable_realtime_sync:
            # Check if API configurations are set
            has_multi_device_config = self.api_configurations and len(self.api_configurations) > 0

            if not has_multi_device_config:
                frappe.throw("Please configure at least one API Configuration when sync is enabled")

            # Validate each API configuration entry
            for idx, config in enumerate(self.api_configurations, start=1):
                if not config.api_url:
                    frappe.throw(f"API URL is required for configuration row {idx}")
                if not config.api_key:
                    frappe.throw(f"API Key is required for configuration row {idx}")
                if not config.api_secret:
                    frappe.throw(f"API Secret is required for configuration row {idx}")

        # Ensure API URL ends with / for all configurations
        if self.api_configurations:
            for config in self.api_configurations:
                if config.api_url and not config.api_url.endswith('/'):
                    config.api_url += '/'

    @frappe.whitelist()
    def sync_now(self):
        """Manually trigger sync"""
        try:
            if not self.enable_realtime_sync:
                return {"success": False, "error": "CrossChex sync is not enabled"}

            # Sync all configured devices
            if self.api_configurations and len(self.api_configurations) > 0:
                total_processed = 0
                total_errors = 0
                sync_results = []

                for config in self.api_configurations:
                    try:
                        result = sync_individual_device(
                            api_url=config.api_url,
                            api_key=config.api_key,
                            config_row_name=config.name,
                            config_name=config.configuration_name
                        )

                        if result.get("success"):
                            total_processed += result.get("processed", 0)
                            sync_results.append(f"{config.configuration_name}: {result.get('processed', 0)} records")
                        else:
                            total_errors += 1
                            sync_results.append(f"{config.configuration_name}: Error - {result.get('error', 'Unknown')}")

                    except Exception as e:
                        total_errors += 1
                        sync_results.append(f"{config.configuration_name}: Exception - {str(e)}")

                # Update sync status
                status_message = f"Manual sync: Processed {total_processed} records from {len(self.api_configurations)} devices"
                self.db_set('last_sync_time', now_datetime(), update_modified=False)
                self.db_set('last_sync_status', status_message, update_modified=False)
                frappe.db.commit()

                return {
                    "success": True,
                    "message": status_message,
                    "details": sync_results
                }
            else:
                return {"success": False, "error": "No API configurations found"}

        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            self.db_set('last_sync_status', error_msg, update_modified=False)
            frappe.db.commit()

            return {"success": False, "error": error_msg}

    @frappe.whitelist()
    def reset_token(self):
        """Reset/clear the current token"""
        try:
            self.db_set('token', None, update_modified=False)
            self.db_set('token_expires', None, update_modified=False)
            self.db_set('connection_status', 'Not Tested', update_modified=False)
            frappe.db.commit()

            return {"success": True, "message": "Token has been reset"}

        except Exception as e:
            return {"success": False, "error": f"Failed to reset token: {str(e)}"}

    @frappe.whitelist()
    def clear_logs(self):
        """Clear CrossChex logs"""
        try:
            # Delete old CrossChex logs if the doctype exists
            if frappe.db.exists("DocType", "CrossChex Log"):
                cutoff_date = get_datetime() - timedelta(days=int(self.log_retention_days or 30))

                frappe.db.sql("""
                    DELETE FROM `tabCrossChex Log`
                    WHERE creation < %s
                """, (cutoff_date,))

                frappe.db.commit()

            return {"success": True, "message": f"Logs older than {self.log_retention_days or 30} days have been cleared"}

        except Exception as e:
            return {"success": False, "error": f"Failed to clear logs: {str(e)}"}


@frappe.whitelist()
def test_individual_api_config(api_url, api_key, config_row_name, config_name=None):
    """Test an individual API configuration"""
    try:
        import uuid

        # Retrieve the actual password from the child table row
        try:
            config_doc = frappe.get_doc("CrossChex API Configuration", config_row_name)
            api_secret = config_doc.get_password('api_secret')
        except Exception as e:
            return {"success": False, "error": f"Failed to retrieve API Secret: {str(e)}"}

        if not api_secret:
            return {"success": False, "error": "API Secret not found. Please enter the API Secret and save the document first."}

        request_id = str(uuid.uuid4())

        # Ensure API URL ends with /
        if not api_url.endswith('/'):
            api_url += '/'

        payload = {
            "header": {
                "nameSpace": "authorize.token",
                "nameAction": "token",
                "version": "1.0",
                "requestId": request_id,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
            },
            "payload": {
                "api_key": api_key,
                "api_secret": api_secret
            }
        }

        response = requests.post(
            api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()

            # Check for error response
            if 'header' in data and data['header'].get('nameSpace') == 'System':
                error_type = data.get('payload', {}).get('type', 'Unknown')
                error_message = data.get('payload', {}).get('message', 'Unknown error')

                if error_type == 'AUTH_ERROR':
                    return {"success": False, "error": "Authentication failed. Please verify your API Key and API Secret."}
                else:
                    return {"success": False, "error": f"{error_type}: {error_message}"}

            # Success response
            elif 'payload' in data and 'token' in data['payload']:
                expires_raw = data['payload'].get('expires')
                expires_formatted = None

                # Convert ISO 8601 datetime with timezone to MySQL-compatible format
                if expires_raw:
                    try:
                        from dateutil import parser
                        dt = parser.parse(expires_raw)
                        expires_formatted = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        expires_formatted = None

                return {
                    "success": True,
                    "token": data['payload']['token'],
                    "expires": expires_formatted,
                    "message": f"Connection to {config_name or api_url} successful!"
                }

        return {"success": False, "error": f"API returned status {response.status_code}: {response.text}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_crosschex_status():
    """Get current CrossChex sync status"""
    try:
        if not frappe.db.exists("DocType", "Crosschex Settings"):
            return {"error": "Crosschex Settings doctype not found"}

        settings = frappe.get_single("Crosschex Settings")

        return {
            "sync_enabled": settings.enable_realtime_sync,
            "last_sync": settings.last_sync_time,
            "last_status": settings.last_sync_status,
            "connection_status": settings.connection_status,
            "api_configured": bool(settings.api_configurations and len(settings.api_configurations) > 0),
            "device_count": len(settings.api_configurations) if settings.api_configurations else 0
        }

    except Exception as e:
        return {"error": f"Error getting status: {str(e)}"}


@frappe.whitelist()
def sync_individual_device(api_url, api_key, config_row_name, config_name=None):
    """Sync attendance data from a specific CrossChex device configuration"""
    try:
        import uuid

        # Retrieve the actual password from the child table row
        try:
            config_doc = frappe.get_doc("CrossChex API Configuration", config_row_name)
            api_secret = config_doc.get_password('api_secret')
        except Exception as e:
            return {"success": False, "error": f"Failed to retrieve API Secret: {str(e)}"}

        if not api_secret:
            return {"success": False, "error": "API Secret not found. Please enter the API Secret and save the document first."}

        # Ensure API URL ends with /
        if not api_url.endswith('/'):
            api_url += '/'

        # Step 1: Generate or retrieve token
        token = None
        token_expires = None

        try:
            token = config_doc.get_password('token')
        except Exception as e:
            frappe.logger().info(f"Token not found for config {config_row_name}: {str(e)}")

        try:
            token_expires = config_doc.token_expires
        except:
            pass

        # Check if token is valid
        needs_new_token = True
        if token and token_expires:
            try:
                expires_dt = get_datetime(token_expires)
                if expires_dt > now_datetime():
                    needs_new_token = False
            except:
                pass

        # Generate new token if needed
        if needs_new_token:
            request_id = str(uuid.uuid4())

            payload = {
                "header": {
                    "nameSpace": "authorize.token",
                    "nameAction": "token",
                    "version": "1.0",
                    "requestId": request_id,
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
                },
                "payload": {
                    "api_key": api_key,
                    "api_secret": api_secret
                }
            }

            response = requests.post(
                api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()

                # Check for error response
                if 'header' in data and data['header'].get('nameSpace') == 'System':
                    error_type = data.get('payload', {}).get('type', 'Unknown')
                    error_message = data.get('payload', {}).get('message', 'Unknown error')
                    return {"success": False, "error": f"Authentication failed: {error_type} - {error_message}"}

                # Success response
                elif 'payload' in data and 'token' in data['payload']:
                    token = data['payload']['token']
                    expires_raw = data['payload'].get('expires')

                    # Save token to database
                    config_doc.db_set('token', token, update_modified=False)

                    if expires_raw:
                        try:
                            from dateutil import parser
                            dt = parser.parse(expires_raw)
                            expires_formatted = dt.strftime('%Y-%m-%d %H:%M:%S')
                            config_doc.db_set('token_expires', expires_formatted, update_modified=False)
                        except:
                            pass

                    config_doc.db_set('last_token_generated', now_datetime(), update_modified=False)
                    frappe.db.commit()
                else:
                    return {"success": False, "error": "Failed to generate token"}
            else:
                return {"success": False, "error": f"API returned status {response.status_code}"}

        # Step 2: Fetch attendance data
        end_time = datetime.utcnow()
        # Use last sync time if available, otherwise fetch last 7 days
        last_sync = config_doc.last_sync_time
        if last_sync:
            try:
                # Fetch from last sync time minus 1 hour (for overlap/safety)
                begin_time = get_datetime(last_sync) - timedelta(hours=1)
                # Convert to UTC
                if begin_time > end_time:
                    begin_time = end_time - timedelta(days=7)
            except:
                begin_time = end_time - timedelta(days=7)
        else:
            # Initial sync: get last 30 days of data
            begin_time = end_time - timedelta(days=30)

        begin_time_str = begin_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")

        # Log the time range being synced
        frappe.logger().info(
            f"CrossChex Sync: Fetching records for {config_name or api_url} "
            f"from {begin_time_str} to {end_time_str}"
        )

        request_id = str(uuid.uuid4())

        payload = {
            "header": {
                "nameSpace": "attendance.record",
                "nameAction": "getrecord",
                "version": "1.0",
                "requestId": request_id,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
            },
            "authorize": {
                "type": "token",
                "token": token
            },
            "payload": {
                "begin_time": begin_time_str,
                "end_time": end_time_str,
                "order": "asc",
                "page": 1,
                "per_page": 1000
            }
        }

        response = requests.post(
            api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )

        if response.status_code != 200:
            return {"success": False, "error": f"Failed to fetch attendance data: {response.status_code}"}

        data = response.json()

        # Check for rate limiting or API errors
        if 'payload' not in data:
            if data.get('type') == 'FREQUENT_REQUEST':
                error_msg = "Rate limit exceeded: The CrossChex API allows requests only once every 30 seconds. Please wait and try again."
                frappe.logger().warning(f"CrossChex rate limit: {data.get('message')}")
                return {"success": False, "error": error_msg}

            error_msg = f"API Error: {data.get('message', 'Unknown error')}"
            frappe.logger().error(f"CrossChex API error - Response: {json.dumps(data, indent=2)}")
            return {"success": False, "error": error_msg}

        if 'list' not in data['payload']:
            if data['payload'].get('type') == 'FREQUENT_REQUEST':
                error_msg = "Rate limit exceeded: The CrossChex API allows requests only once every 30 seconds. Please wait and try again."
                return {"success": False, "error": error_msg}

            error_msg = f"No attendance data returned. Payload: {data['payload'].get('message', 'Unknown error')}"
            return {"success": False, "error": error_msg}

        records = data['payload']['list']

        # Log sync info
        log_msg = f"CrossChex API returned {len(records)} records from {config_name or api_url}"
        frappe.logger().info(log_msg)

        if records:
            range_msg = f"CrossChex Sync: Record range - first: {records[0].get('checktime', 'N/A')}, last: {records[-1].get('checktime', 'N/A')}"
            frappe.logger().info(range_msg)

        # Step 3: Process attendance records
        processed_count = 0
        errors = []
        skipped_no_employee = 0
        skipped_duplicate = 0

        # Checktype mapping
        logMap = {
            0: "IN",
            1: "OUT",
            128: "IN",
            129: "OUT"
        }

        for record in records:
            try:
                # Extract data from CrossChex record
                employee_data = record.get('employee', {})
                # emp_code is the primary field used by CrossChex Cloud API
                user_id = record.get('emp_code') or employee_data.get('workno') or record.get('emp_pin') or record.get('userid') or record.get('user_id')
                check_time = record.get('checktime') or record.get('check_time')

                # Handle both field names for checktype
                log_type_raw = record.get('checktype') if 'checktype' in record else record.get('check_type', 0)

                # Get device info
                device_data = record.get('device', {})
                device_id = device_data.get('name') or device_data.get('serial_number') or config_name or 'CrossChex'

                if not user_id or not check_time:
                    errors.append("Missing workno/userid or checktime")
                    continue

                # Convert to int for comparison with attendance_device_id
                try:
                    user_id_int = int(user_id)
                except (ValueError, TypeError):
                    errors.append(f"Invalid workno format: {user_id}")
                    continue

                # Find ACTIVE employee by attendance_device_id (workno)
                employee = frappe.db.get_value('Employee',
                    {'attendance_device_id': user_id_int, 'status': 'Active'},
                    ['name', 'employee_name'],
                    as_dict=True
                )

                if not employee:
                    skipped_no_employee += 1
                    continue

                # Parse check time
                try:
                    check_datetime = get_datetime(check_time)
                    # Convert to naive datetime (remove timezone) for Frappe compatibility
                    if check_datetime.tzinfo is not None:
                        check_datetime = check_datetime.replace(tzinfo=None)
                except Exception as time_error:
                    errors.append(f"Invalid datetime format: {check_time}")
                    continue

                # Map checktype using logMap
                frappe_log_type = logMap.get(log_type_raw, 'IN')

                # Check if this checkin already exists (avoid duplicates by employee + time)
                existing = frappe.db.exists('Employee Checkin', {
                    'employee': employee.name,
                    'time': check_datetime
                })

                if existing:
                    skipped_duplicate += 1
                    continue

                # Create Employee Checkin
                try:
                    checkin_doc = frappe.new_doc('Employee Checkin')
                    checkin_doc.employee = employee.name
                    checkin_doc.log_type = frappe_log_type
                    checkin_doc.device_id = device_id
                    checkin_doc.time = check_datetime
                    checkin_doc.skip_auto_attendance = 1

                    # Log before insert
                    frappe.logger().info(
                        f"CrossChex: Creating checkin for {employee.employee_name} "
                        f"at {check_datetime} ({frappe_log_type})"
                    )

                    checkin_doc.insert(ignore_permissions=True)
                    frappe.db.commit()
                    
                    # Log after successful insert
                    frappe.logger().info(
                        f"CrossChex: Successfully created checkin {checkin_doc.name} "
                        f"for {employee.employee_name}"
                    )
                    
                    processed_count += 1

                except Exception as insert_error:
                    error_msg = f"Failed to create checkin for {employee.employee_name} at {check_datetime}: {str(insert_error)}"
                    errors.append(error_msg)
                    frappe.logger().error(f"CrossChex Insert Error: {error_msg}")
                    # Log full traceback for debugging
                    import traceback
                    frappe.logger().error(f"CrossChex Traceback: {traceback.format_exc()}")
                    continue

            except Exception as e:
                errors.append(f"Error processing record: {str(e)}")
                frappe.logger().error(f"CrossChex sync error: {str(e)}")
                continue

        # Log summary
        frappe.logger().info(
            f"CrossChex Sync Summary for {config_name}: "
            f"Total: {len(records)}, Created: {processed_count}, "
            f"No Employee: {skipped_no_employee}, Duplicate: {skipped_duplicate}, Errors: {len(errors)}"
        )

        # Update last sync time on the config row
        config_doc.db_set('last_sync_time', now_datetime(), update_modified=False)
        config_doc.db_set('last_sync_status', f"Success - {processed_count} records processed", update_modified=False)
        frappe.db.commit()

        return {
            "success": True,
            "processed": processed_count,
            "errors": len(errors),
            "error_details": errors[:10] if errors else [],  # Show first 10 errors
            "skipped_no_employee": skipped_no_employee,
            "skipped_duplicate": skipped_duplicate,
            "message": f"Successfully synced {processed_count} attendance records from {config_name or api_url}"
        }

    except Exception as e:
        frappe.log_error(f"Individual device sync failed: {str(e)}", "CrossChex Sync Error")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def full_resync_device(api_url, api_key, config_row_name, config_name=None):
    """Full resync - fetches last 30 days of attendance data"""
    try:
        import uuid

        # Retrieve the actual password from the child table row
        try:
            config_doc = frappe.get_doc("CrossChex API Configuration", config_row_name)
            api_secret = config_doc.get_password('api_secret')
        except Exception as e:
            return {"success": False, "error": f"Failed to retrieve API Secret: {str(e)}"}

        if not api_secret:
            return {"success": False, "error": "API Secret not found"}

        # Ensure API URL ends with /
        if not api_url.endswith('/'):
            api_url += '/'

        # Generate token
        request_id = str(uuid.uuid4())

        payload = {
            "header": {
                "nameSpace": "authorize.token",
                "nameAction": "token",
                "version": "1.0",
                "requestId": request_id,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
            },
            "payload": {
                "api_key": api_key,
                "api_secret": api_secret
            }
        }

        response = requests.post(
            api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )

        if response.status_code != 200:
            return {"success": False, "error": f"Token generation failed: {response.status_code}"}

        data = response.json()
        if 'payload' not in data or 'token' not in data['payload']:
            return {"success": False, "error": "Failed to generate token"}

        token = data['payload']['token']

        # Fetch last 30 days of data
        end_time = datetime.utcnow()
        begin_time = end_time - timedelta(days=30)

        begin_time_str = begin_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")

        frappe.logger().info(f"CrossChex Full Resync: Fetching 30 days of data for {config_name}")

        request_id = str(uuid.uuid4())

        payload = {
            "header": {
                "nameSpace": "attendance.record",
                "nameAction": "getrecord",
                "version": "1.0",
                "requestId": request_id,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
            },
            "authorize": {
                "type": "token",
                "token": token
            },
            "payload": {
                "begin_time": begin_time_str,
                "end_time": end_time_str,
                "order": "asc",
                "page": 1,
                "per_page": 1000
            }
        }

        response = requests.post(
            api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )

        if response.status_code != 200:
            return {"success": False, "error": f"Failed to fetch attendance: {response.status_code}"}

        data = response.json()

        if 'payload' not in data or 'list' not in data['payload']:
            return {"success": False, "error": "No attendance data in response"}

        records = data['payload']['list']
        frappe.logger().info(f"CrossChex Full Resync: Found {len(records)} records")

        # Process records (same logic as sync_individual_device)
        processed_count = 0
        skipped_no_employee = 0
        skipped_duplicate = 0

        logMap = {0: "IN", 1: "OUT", 128: "IN", 129: "OUT"}

        for record in records:
            try:
                employee_data = record.get('employee', {})
                # emp_code is the primary field used by CrossChex Cloud API
                user_id = record.get('emp_code') or employee_data.get('workno') or record.get('emp_pin') or record.get('userid') or record.get('user_id')
                check_time = record.get('checktime') or record.get('check_time')
                log_type_raw = record.get('checktype') if 'checktype' in record else record.get('check_type', 0)

                device_data = record.get('device', {})
                device_id = device_data.get('name') or config_name or 'CrossChex'

                if not user_id or not check_time:
                    continue

                try:
                    user_id_int = int(user_id)
                except (ValueError, TypeError):
                    continue

                employee = frappe.db.get_value('Employee',
                    {'attendance_device_id': user_id_int, 'status': 'Active'},
                    ['name', 'employee_name'],
                    as_dict=True
                )

                if not employee:
                    skipped_no_employee += 1
                    continue

                check_datetime = get_datetime(check_time)
                if check_datetime.tzinfo is not None:
                    check_datetime = check_datetime.replace(tzinfo=None)

                frappe_log_type = logMap.get(log_type_raw, 'IN')

                existing = frappe.db.exists('Employee Checkin', {
                    'employee': employee.name,
                    'time': check_datetime
                })

                if existing:
                    skipped_duplicate += 1
                    continue

                checkin_doc = frappe.new_doc('Employee Checkin')
                checkin_doc.employee = employee.name
                checkin_doc.log_type = frappe_log_type
                checkin_doc.device_id = device_id
                checkin_doc.time = check_datetime
                checkin_doc.skip_auto_attendance = 1

                checkin_doc.insert(ignore_permissions=True)
                frappe.db.commit()
                processed_count += 1

            except Exception as e:
                frappe.logger().error(f"Error in full resync: {str(e)}")
                continue

        # Update sync status
        config_doc.db_set('last_sync_time', now_datetime(), update_modified=False)
        config_doc.db_set('last_sync_status', f"Full resync - {processed_count} records", update_modified=False)
        frappe.db.commit()

        return {
            "success": True,
            "processed": processed_count,
            "skipped_no_employee": skipped_no_employee,
            "skipped_duplicate": skipped_duplicate,
            "message": f"Full resync completed: {processed_count} records created, {skipped_duplicate} duplicates skipped"
        }

    except Exception as e:
        frappe.log_error(f"Full resync failed: {str(e)}", "CrossChex Full Resync Error")
        return {"success": False, "error": str(e)}


def scheduled_attendance_sync():
    """Scheduled function for attendance sync - syncs all configured devices"""
    try:
        if not frappe.db.exists("DocType", "Crosschex Settings"):
            return

        settings = frappe.get_single("Crosschex Settings")
        if not settings.enable_realtime_sync:
            return

        # Check if we have API configurations (multi-device setup)
        if settings.api_configurations and len(settings.api_configurations) > 0:
            total_processed = 0
            total_errors = 0
            sync_results = []

            for config in settings.api_configurations:
                try:
                    result = sync_individual_device(
                        api_url=config.api_url,
                        api_key=config.api_key,
                        config_row_name=config.name,
                        config_name=config.configuration_name
                    )

                    if result.get("success"):
                        total_processed += result.get("processed", 0)
                        sync_results.append(f"{config.configuration_name}: {result.get('processed', 0)} records")
                    else:
                        total_errors += 1
                        sync_results.append(f"{config.configuration_name}: Error - {result.get('error', 'Unknown')}")

                except Exception as e:
                    total_errors += 1
                    sync_results.append(f"{config.configuration_name}: Exception - {str(e)}")
                    frappe.logger().error(f"Error syncing device {config.configuration_name}: {str(e)}")

            # Update settings with sync summary
            status_message = f"Auto-sync: Processed {total_processed} records from {len(settings.api_configurations)} devices"
            settings.db_set('last_sync_time', now_datetime(), update_modified=False)
            settings.db_set('last_sync_status', status_message[:255], update_modified=False)
            frappe.db.commit()

    except Exception as e:
        frappe.logger().error(f"Error in scheduled_attendance_sync: {str(e)}")


def check_and_refresh_token():
    """Scheduled function to check and refresh tokens for all devices"""
    try:
        if not frappe.db.exists("DocType", "Crosschex Settings"):
            return

        settings = frappe.get_single("Crosschex Settings")
        if not settings.enable_realtime_sync:
            return

        # Refresh tokens for all API configurations
        if settings.api_configurations and len(settings.api_configurations) > 0:
            for config in settings.api_configurations:
                try:
                    config_doc = frappe.get_doc("CrossChex API Configuration", config.name)

                    token = None
                    token_expires = None

                    try:
                        token = config_doc.get_password('token')
                    except:
                        pass

                    try:
                        token_expires = config_doc.token_expires
                    except:
                        pass

                    needs_refresh = False
                    if not token:
                        needs_refresh = True
                    elif token_expires:
                        try:
                            expires_dt = get_datetime(token_expires)
                            # Refresh if expires within next 30 minutes
                            if (expires_dt - now_datetime()).total_seconds() <= 1800:
                                needs_refresh = True
                        except:
                            needs_refresh = True

                    if needs_refresh:
                        test_individual_api_config(
                            api_url=config.api_url,
                            api_key=config.api_key,
                            config_row_name=config.name,
                            config_name=config.configuration_name
                        )

                except Exception as e:
                    frappe.logger().error(f"Error refreshing token for {config.configuration_name}: {str(e)}")

    except Exception as e:
        frappe.logger().error(f"Error in check_and_refresh_token: {str(e)}")
