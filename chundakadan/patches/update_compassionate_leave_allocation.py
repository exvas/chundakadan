# Copyright (c) 2026, Chundakadan
# License: MIT

import frappe
from frappe.utils import flt


def execute():
    """
    Update new_leaves_allocated field in existing Leave Allocation documents
    for Compassionate Leave type.
    
    This patch fixes existing allocations that were created with incorrect values
    (0 or pro-rated values) instead of the full allocation from Leave Policy.
    """
    
    # Get the max_leaves_allowed from Leave Type as the correct value
    max_leaves_allowed = frappe.db.get_value(
        "Leave Type", 
        "Compassionate Leave", 
        "max_leaves_allowed"
    )
    
    if not max_leaves_allowed:
        print("Compassionate Leave type not found or max_leaves_allowed not set. Skipping patch.")
        return
    
    print(f"Compassionate Leave max_leaves_allowed: {max_leaves_allowed}")
    
    # Get all Leave Allocation documents for Compassionate Leave
    allocations = frappe.get_all(
        "Leave Allocation",
        filters={
            "leave_type": "Compassionate Leave",
            "docstatus": ["in", [0, 1]]  # Draft or Submitted
        },
        fields=["name", "employee", "new_leaves_allocated", "total_leaves_allocated", "unused_leaves", "docstatus"]
    )
    
    updated_count = 0
    
    for alloc in allocations:
        # Only update if current value is different from max_leaves_allowed
        if flt(alloc.new_leaves_allocated) != flt(max_leaves_allowed):
            # Calculate new total_leaves_allocated
            unused_leaves = flt(alloc.unused_leaves) or 0
            new_total = flt(max_leaves_allowed) + unused_leaves
            
            # Update the Leave Allocation directly in database
            frappe.db.set_value(
                "Leave Allocation",
                alloc.name,
                {
                    "new_leaves_allocated": max_leaves_allowed,
                    "total_leaves_allocated": new_total
                },
                update_modified=False
            )
            
            print(f"Updated {alloc.name} for employee {alloc.employee}: "
                  f"new_leaves_allocated: {alloc.new_leaves_allocated} -> {max_leaves_allowed}, "
                  f"total_leaves_allocated: {alloc.total_leaves_allocated} -> {new_total}")
            
            updated_count += 1
    
    if updated_count > 0:
        frappe.db.commit()
        print(f"\nSuccessfully updated {updated_count} Compassionate Leave Allocation records.")
    else:
        print("\nNo Compassionate Leave Allocation records needed updating.")
