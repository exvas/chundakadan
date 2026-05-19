# Copyright (c) 2026, Ashkar and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def get_approver_by_role(role):
    """
    Helper function to dynamically fetch the approver user based on the custom role.
    It resolves the enabled User assigned to the specified Role.
    If multiple users exist, it prefers the one linked to an active Employee record.
    
    Args:
        role (str): The custom role name (e.g. 'ASM Leave Approver')
        
    Returns:
        str: Email (user_id) of the matched approver user, or None
    """
    users = frappe.get_all(
        "Has Role",
        filters={"role": role},
        fields=["parent"]
    )
    if not users:
        return None
        
    # 1. Prefer active employees with enabled users
    for u in users:
        user_id = u.parent
        if frappe.db.get_value("User", user_id, "enabled"):
            # Check if user is linked to an active employee
            employee_exists = frappe.db.exists(
                "Employee",
                {"user_id": user_id, "status": "Active"}
            )
            if employee_exists:
                return user_id
                
    # 2. Fallback to the first enabled user
    for u in users:
        user_id = u.parent
        if frappe.db.get_value("User", user_id, "enabled"):
            return user_id
            
    return None


def generate_approval_flow(doc, designation):
    """
    Generates the approval sequence based on the employee's designation,
    populates the child table 'approval_flow', and sets the initial current approver.
    
    Flow Logic:
    - Sales Executive: ASM -> HR -> GM
    - Area Sales Manager: HR -> GM
    - HR Coordinator / Coordinator: GM
    - General Manager: HR
    - Fallback: HR -> GM
    """
    role_sequence = []
    
    if designation == "Sales Executive":
        role_sequence = ["ASM Leave Approver", "HR Leave Approver", "GM Leave Approver"]
    elif designation == "Area Sales Manager":
        role_sequence = ["HR Leave Approver", "GM Leave Approver"]
    elif designation in ["HR Coordinator", "Coordinator"]:
        role_sequence = ["GM Leave Approver"]
    elif designation == "General Manager":
        role_sequence = ["HR Leave Approver"]
    else:
        # Extensible Fallback: Default to HR Coordinator then General Manager approvals
        role_sequence = ["HR Leave Approver", "GM Leave Approver"]
        
    # Clear the existing approval flow child table
    doc.set("approval_flow", [])
    
    # Populate the approval flow child table
    for role in role_sequence:
        approver = get_approver_by_role(role)
        if not approver:
            frappe.throw(
                _("Could not locate an active user with the role '{0}'. Please make sure a user is configured with this role and linked to an active Employee.").format(role)
            )
            
        doc.append("approval_flow", {
            "approver": approver,
            "approver_role": role,
            "status": "Pending"
        })
        
    # Set the initial state
    if doc.approval_flow:
        doc.current_approval_index = 0
        doc.current_approver = doc.approval_flow[0].approver
        doc.custom_approval_status = "Pending"
    else:
        doc.current_approval_index = 0
        doc.current_approver = None
        doc.custom_approval_status = "Pending"


def validate_leave(doc, method=None):
    """
    Hook triggered on validation of Leave Application.
    Detects the designation of the employee and generates the approval chain dynamically.
    """
    # Do not execute if document is already submitted or cancelled
    if doc.docstatus > 0:
        return
        
    if not doc.employee:
        return
        
    designation = frappe.db.get_value("Employee", doc.employee, "designation")
    
    # Auto generate approval flow on creation or when employee changes
    if doc.is_new():
        generate_approval_flow(doc, designation)
    else:
        # Check if the employee has changed
        db_employee = frappe.db.get_value("Leave Application", doc.name, "employee")
        if db_employee != doc.employee or not doc.approval_flow:
            generate_approval_flow(doc, designation)


@frappe.whitelist()
def approve_leave(docname):
    """
    Whitelisted API method to approve the current level of leave application.
    Marks the current approver row as Approved, updates the approved_on timestamp,
    and forwards to the next approver or finalizes the document submission.
    """
    # Load the document
    doc = frappe.get_doc("Leave Application", docname)
    current_user = frappe.session.user
    
    # Security Validation: Only the designated current approver or Administrator can approve
    if current_user != doc.current_approver and current_user != "Administrator":
        frappe.throw(
            _("You are not authorized to approve this leave application. Current approver is: {0}").format(doc.current_approver)
        )
        
    if doc.custom_approval_status in ["Approved", "Rejected"]:
        frappe.throw(
            _("This leave application has already been processed (Status: {0}).").format(doc.custom_approval_status)
        )
        
    idx = doc.current_approval_index
    if not doc.approval_flow or idx >= len(doc.approval_flow):
        frappe.throw(_("The approval flow is empty or current index is out of bounds."))
        
    # Mark the current row approved
    row = doc.approval_flow[idx]
    row.status = "Approved"
    row.approved_on = frappe.utils.now_datetime()
    
    # Advance to the next level
    next_idx = idx + 1
    if next_idx < len(doc.approval_flow):
        doc.current_approval_index = next_idx
        doc.current_approver = doc.approval_flow[next_idx].approver
        doc.custom_approval_status = "Partially Approved"
        
        # Save modifications bypassing standard permissions for the approver
        doc.flags.ignore_permissions = True
        doc.save()
        
        # Notify the user
        frappe.msgprint(
            _("Leave Application partially approved and successfully routed to {0}.").format(doc.current_approver),
            indicator="blue"
        )
    else:
        # Final approval: Set custom status, clear current approver, set standard status and submit
        doc.custom_approval_status = "Approved"
        doc.current_approver = None
        doc.status = "Approved"
        
        doc.flags.ignore_permissions = True
        doc.flags.ignore_validate = True
        doc.save()
        doc.submit()
        
        frappe.msgprint(
            _("Leave Application has been fully approved and submitted!"),
            indicator="green"
        )
        
    return {"success": True}


@frappe.whitelist()
def reject_leave(docname, remarks=None):
    """
    Whitelisted API method to reject the leave application.
    Marks the current level as Rejected, updates status, and stops the flow.
    """
    doc = frappe.get_doc("Leave Application", docname)
    current_user = frappe.session.user
    
    # Security Validation: Only the designated current approver or Administrator can reject
    if current_user != doc.current_approver and current_user != "Administrator":
        frappe.throw(
            _("You are not authorized to reject this leave application. Current approver is: {0}").format(doc.current_approver)
        )
        
    if doc.custom_approval_status in ["Approved", "Rejected"]:
        frappe.throw(
            _("This leave application has already been processed (Status: {0}).").format(doc.custom_approval_status)
        )
        
    idx = doc.current_approval_index
    if not doc.approval_flow or idx >= len(doc.approval_flow):
        frappe.throw(_("The approval flow is empty or current index is out of bounds."))
        
    # Mark the current row rejected
    row = doc.approval_flow[idx]
    row.status = "Rejected"
    row.approved_on = frappe.utils.now_datetime()
    if remarks:
        row.remarks = remarks
        
    # Finalize rejection
    doc.custom_approval_status = "Rejected"
    doc.status = "Rejected"
    doc.current_approver = None
    
    doc.flags.ignore_permissions = True
    doc.save()
    
    frappe.msgprint(
        _("Leave Application has been rejected."),
        indicator="red"
    )
    
    return {"success": True}


def get_permission_query_conditions(user=None):
    """
    Custom permission query conditions for Leave Application.
    Ensures employees see their own applications, while current approvers can see their pending ones.
    """
    if not user:
        user = frappe.session.user
        
    if user == "Administrator" or "System Manager" in frappe.get_roles(user) or "HR Manager" in frappe.get_roles(user):
        return ""
        
    return f"(`tabLeave Application`.owner = {frappe.db.escape(user)} OR `tabLeave Application`.current_approver = {frappe.db.escape(user)})"


def has_permission(doc, ptype="read", user=None):
    """
    Custom document-level permission verification.
    Grants access if the user is the owner, a current/past approver, or holds elevated manager roles.
    """
    if not user:
        user = frappe.session.user
        
    if user == "Administrator" or "System Manager" in frappe.get_roles(user) or "HR Manager" in frappe.get_roles(user):
        return True
        
    if doc.owner == user or doc.current_approver == user:
        return True
        
    # Past approvers from the table can read
    for row in getattr(doc, "approval_flow", []):
        if row.approver == user:
            return True
            
    return False
