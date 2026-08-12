import frappe
from hrms.hr.doctype.employee_checkin.employee_checkin import EmployeeCheckin


class CustomEmployeeCheckin(EmployeeCheckin):
    """Exempt biometric/device check-ins from GPS geofencing.

    HR Settings.allow_geolocation_tracking (a MOBILE geofencing feature) makes
    HRMS require latitude/longitude on EVERY Employee Checkin and validate the
    distance from the employee's Shift Location. Biometric device punches — e.g.
    synced from CrossChex — are physically verified by the device itself and
    carry no GPS coordinates, so they were being rejected with
    "Latitude and longitude values are required for checking in." and attendance
    never reached ERPNext.

    A check-in that has a device_id but no latitude/longitude is a device punch:
    skip geolocation validation for it. Mobile check-ins always carry GPS, so
    they still go through the full geofence distance check unchanged.
    """

    def validate_distance_from_shift_location(self):
        if self.device_id and not (self.latitude or self.longitude):
            return
        return super().validate_distance_from_shift_location()
