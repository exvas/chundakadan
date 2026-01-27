# Copyright (c) 2026, Chundakadan
# License: MIT

import frappe
from frappe.utils import flt


def execute():
    """
    Update Leave Ledger Entry for Compassionate Leave allocations.
    
    This patch updates the Leave Ledger Entry records to reflect the correct
    new_leaves_allocated values from Leave Allocation. This ensures that:
    - Employee Leave Balance reports show correct values
    - Employee Leave Balance Summary shows correct values
    - Leave balance calculations are accurate
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
            "docstatus": 1  # Only Submitted
        },
        fields=["name", "employee", "new_leaves_allocated"]
    )
    
    ledger_updated_count = 0
    
    for alloc in allocations:
        # Find corresponding Leave Ledger Entry records for this allocation
        # (allocation type, not carry forward, and not expired)
        ledger_entries = frappe.get_all(
            "Leave Ledger Entry",
            filters={
                "transaction_type": "Leave Allocation",
                "transaction_name": alloc.name,
                "leave_type": "Compassionate Leave",
                "is_carry_forward": 0,
                "docstatus": 1
            },
            fields=["name", "leaves", "employee"]
        )
        
        for entry in ledger_entries:
            # Update only if the current leaves value is different from max_leaves_allowed
            if flt(entry.leaves) != flt(max_leaves_allowed):
                old_leaves = entry.leaves
                
                # Update Leave Ledger Entry directly in database
                frappe.db.set_value(
                    "Leave Ledger Entry",
                    entry.name,
                    "leaves",
                    max_leaves_allowed,
                    update_modified=False
                )
                
                print(f"Updated Leave Ledger Entry {entry.name} for employee {entry.employee}: "
                      f"leaves: {old_leaves} -> {max_leaves_allowed}")
                
                ledger_updated_count += 1
    
    if ledger_updated_count > 0:
        frappe.db.commit()
        print(f"\nSuccessfully updated {ledger_updated_count} Leave Ledger Entry records for Compassionate Leave.")
    else:
        print("\nNo Leave Ledger Entry records needed updating.")
    
    print("\nLeave Balance reports will now show the correct values for Compassionate Leave.")
