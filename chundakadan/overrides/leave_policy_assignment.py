# Copyright (c) 2026, Chundakadan
# License: MIT

import frappe
from frappe.utils import flt
from hrms.hr.doctype.leave_policy_assignment.leave_policy_assignment import LeavePolicyAssignment


class CustomLeavePolicyAssignment(LeavePolicyAssignment):
    """
    Custom Leave Policy Assignment that overrides the new_leaves calculation
    to use the full annual_allocation from Leave Policy without pro-rating or rounding.
    
    This ensures that:
    - Sick Leave 17.5 is allocated as 17.5 (not rounded to 17)
    - All leave types get their full allocation as defined in Leave Policy
    """
    
    def get_new_leaves(self, annual_allocation, leave_details, date_of_joining):
        """
        Override to return the full annual_allocation without pro-rating or rounding.
        
        The standard HRMS behavior:
        1. Pro-rates leaves if employee joined after effective_from
        2. Rounds the result to nearest integer for non-earned leaves
        
        This override:
        - Returns the full annual_allocation as-is
        - Only sets 0 for compensatory leaves (which are earned when working holidays)
        """
        from frappe.model.meta import get_field_precision
        
        precision = get_field_precision(
            frappe.get_meta("Leave Allocation").get_field("new_leaves_allocated")
        )
        
        # Compensatory leaves should still be 0 as they are earned when working on holidays
        if leave_details.is_compensatory:
            return 0
        
        # For all other leave types, return the full annual allocation without rounding
        return flt(annual_allocation, precision)
