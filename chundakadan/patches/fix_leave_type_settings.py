# Copyright (c) 2026, Chundakadan
# License: MIT

import frappe


def execute():
    """
    Update Leave Type settings to ensure correct leave allocation behavior:
    - Compassionate Leave: is_earned_leave = 0 (allocate full amount, not gradually)
    - Compensatory Off: is_compensatory = 0 (allocate the full amount from Leave Policy)
    
    These settings are required for the Leave Allocation to show the correct values
    from the Leave Policy's annual_allocation field.
    """
    
    # Fix Compassionate Leave - should not be earned leave
    if frappe.db.exists("Leave Type", "Compassionate Leave"):
        frappe.db.set_value(
            "Leave Type", 
            "Compassionate Leave", 
            "is_earned_leave", 
            0,
            update_modified=False
        )
        print("Updated Compassionate Leave: is_earned_leave = 0")
    
    # Fix Compensatory Off - should not be compensatory type
    if frappe.db.exists("Leave Type", "Compensatory Off"):
        frappe.db.set_value(
            "Leave Type", 
            "Compensatory Off", 
            "is_compensatory", 
            0,
            update_modified=False
        )
        print("Updated Compensatory Off: is_compensatory = 0")
    
    frappe.db.commit()
    print("Leave Type settings updated successfully for correct Leave Allocation behavior.")
