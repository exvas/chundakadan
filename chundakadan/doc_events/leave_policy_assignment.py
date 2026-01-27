# Copyright (c) 2026, Chundakadan
# License: MIT

import frappe


def update_new_leaves_from_max_allowed(doc, method):
    """
    Before Leave Policy Assignment is submitted, ensure that the Leave Policy
    has correct annual_allocation values fetched from max_leaves_allowed of Leave Types.
    This is a safeguard to ensure Leave Allocations are created with correct values.
    """
    leave_policy = frappe.get_doc("Leave Policy", doc.leave_policy)
    updated = False
    
    for detail in leave_policy.leave_policy_details:
        if detail.leave_type:
            max_leaves_allowed = frappe.db.get_value(
                "Leave Type", detail.leave_type, "max_leaves_allowed"
            )
            
            if max_leaves_allowed and max_leaves_allowed > 0:
                if not detail.annual_allocation or detail.annual_allocation != max_leaves_allowed:
                    detail.annual_allocation = max_leaves_allowed
                    updated = True
    
    if updated:
        leave_policy.flags.ignore_permissions = True
        leave_policy.save()
        frappe.msgprint(
            frappe._("Leave Policy '{0}' has been updated with correct annual allocation values from Leave Types.").format(
                doc.leave_policy
            ),
            indicator="blue",
            alert=True
        )
