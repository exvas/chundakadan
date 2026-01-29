# Copyright (c) 2026, Chundakadan
# License: MIT
#code written by niranjana

import frappe


def set_annual_allocation_from_leave_type(doc, method):
    """
    When a Leave Policy is being saved, automatically set the annual_allocation
    for each leave type from the max_leaves_allowed field of the corresponding Leave Type.
    This ensures that Leave Allocations created from Leave Policy Assignment
    will have the correct new_leaves_allocated value.
    """
    if not doc.leave_policy_details:
        return

    for detail in doc.leave_policy_details:
        if detail.leave_type:
            max_leaves_allowed = frappe.db.get_value(
                "Leave Type", detail.leave_type, "max_leaves_allowed"
            )
            
            # Only set if max_leaves_allowed is defined and annual_allocation is not set or is 0
            if max_leaves_allowed and max_leaves_allowed > 0:
                # Always update to ensure it matches the Leave Type's max_leaves_allowed
                if not detail.annual_allocation or detail.annual_allocation != max_leaves_allowed:
                    detail.annual_allocation = max_leaves_allowed


def validate_leave_policy_details(doc, method):
    """
    Validate that annual_allocation doesn't exceed max_leaves_allowed for each leave type.
    Also alert if max_leaves_allowed is not set in the Leave Type.
    """
    if not doc.leave_policy_details:
        return

    for detail in doc.leave_policy_details:
        if detail.leave_type:
            max_leaves_allowed = frappe.db.get_value(
                "Leave Type", detail.leave_type, "max_leaves_allowed"
            )
            
            # Alert if max_leaves_allowed is not set
            if not max_leaves_allowed or max_leaves_allowed == 0:
                frappe.msgprint(
                    frappe._("Leave Type '{0}' does not have 'Maximum Leave Allocation Allowed' set. "
                            "Please set it in the Leave Type to ensure correct Leave Allocation.").format(
                        detail.leave_type
                    ),
                    indicator="orange",
                    alert=True
                )
