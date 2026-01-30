# Copyright (c) 2026, Chundakadan
# License: MIT
#code written by niranjana nir
import frappe


def execute():
    """
    One-time patch to update all Leave Policy details with correct annual_allocation
    values from the max_leaves_allowed field of corresponding Leave Types.
    
    This fixes the issue where new_leaves_allocated in Leave Allocation was not 
    getting proper values when created via Leave Policy Assignment.
    """
    # Get all Leave Policy Detail records
    leave_policy_details = frappe.get_all(
        "Leave Policy Detail",
        fields=["name", "parent", "leave_type", "annual_allocation"]
    )
    
    updated_count = 0
    
    for detail in leave_policy_details:
        if detail.leave_type:
            max_leaves_allowed = frappe.db.get_value(
                "Leave Type", detail.leave_type, "max_leaves_allowed"
            )
            
            if max_leaves_allowed and max_leaves_allowed > 0:
                if not detail.annual_allocation or detail.annual_allocation != max_leaves_allowed:
                    # Direct database update to bypass submission check
                    frappe.db.set_value(
                        "Leave Policy Detail", 
                        detail.name, 
                        "annual_allocation", 
                        max_leaves_allowed,
                        update_modified=False
                    )
                    updated_count += 1
    
    if updated_count > 0:
        frappe.db.commit()
        print(f"Updated {updated_count} Leave Policy Detail records with correct annual allocation values.")
