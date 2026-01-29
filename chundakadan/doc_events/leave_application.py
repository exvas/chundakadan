import frappe
from frappe import _
#code written by niranjana

# Approver configuration - Email addresses for each approver role
APPROVERS = {
    "HOD": "chundakadannorthasm@gmail.com",
    "HR": "binduudayan334@gmail.com",
    "GM": "chundakadangm@gmail.com"
}

# Status flow definitions for each employee category
# is_final=True means this is the last approval step - set HRMS status to Approved
STATUS_FLOWS = {
    "sales_executive": [
        {"status": "Pending HOD", "next_status": "Approved HOD", "approver": "HOD"},
        {"status": "Approved HOD", "next_status": "Pending HR", "approver": None},
        {"status": "Pending HR", "next_status": "Approved HR", "approver": "HR"},
        {"status": "Approved HR", "next_status": "Pending GM", "approver": None},
        {"status": "Pending GM", "next_status": "Approved GM", "approver": "GM", "is_final": True},
    ],
    "other": [
        {"status": "Pending HR", "next_status": "Approved HR", "approver": "HR"},
        {"status": "Approved HR", "next_status": "Pending GM", "approver": None},
        {"status": "Pending GM", "next_status": "Approved GM", "approver": "GM", "is_final": True},
    ],
    "hod_hr": [
        {"status": "Pending GM", "next_status": "Approved GM", "approver": "GM", "is_final": True},
    ],
    "gm": [
        {"status": "Pending HR", "next_status": "Approved HR", "approver": "HR", "is_final": True},
    ]
}

# Initial status and approver for each category
INITIAL_CONFIG = {
    "sales_executive": {"status": "Pending HOD", "approver": "HOD"},
    "other": {"status": "Pending HR", "approver": "HR"},
    "hod_hr": {"status": "Pending GM", "approver": "GM"},
    "gm": {"status": "Pending HR", "approver": "HR"}
}


def get_employee_role_profile(employee_name):
    """
    Get role_profile_name from User linked to employee.
    First tries to match by full_name, then by User docname.
    """
    if not employee_name:
        return None
    
    # Try matching with User full_name
    user = frappe.db.get_value(
        "User", 
        {"full_name": employee_name}, 
        ["name", "role_profile_name"], 
        as_dict=True
    )
    
    if not user:
        # Try matching with User docname (email)
        user = frappe.db.get_value(
            "User", 
            {"name": employee_name}, 
            ["name", "role_profile_name"], 
            as_dict=True
        )
    
    return user.get("role_profile_name") if user else None


def get_employee_category(role_profile, employee_name=None):
    """
    Determine employee category based on role profile name.
    
    Categories:
    - sales_executive: For Sales Executive role profile
    - hod_hr: For HOD or HR role profiles
    - gm: For GM / General Manager role profile
    - other: All other role profiles
    
    Special cases:
    - Bindu T: Treated as hod_hr (HR) regardless of role profile, 
               so her leaves go directly to GM for approval
    """
    # Special case: Bindu T should be treated as HR (hod_hr category)
    # Her leaves should go directly to GM for approval
    if employee_name and employee_name.strip().lower() == "bindu t":
        return "hod_hr"
    
    if not role_profile:
        return "other"
    
    role_profile_lower = role_profile.lower().strip()
    
    # Check for Sales Executive (partial match)
    if "sales executive" in role_profile_lower or role_profile_lower == "sales executive":
        return "sales_executive"
    
    # Check for GM / General Manager (partial match)
    if role_profile_lower == "gm" or "general manager" in role_profile_lower:
        return "gm"
    
    # Check for HOD (partial match)
    if role_profile_lower == "hod" or "head of department" in role_profile_lower:
        return "hod_hr"
    
    # Check for HR (partial match) - but not if it's part of another word
    if role_profile_lower == "hr" or "human resource" in role_profile_lower:
        return "hod_hr"
    
    return "other"


def get_next_approver_and_status(category, current_status):
    """
    Get the next status and approver based on current status and employee category.
    
    Returns:
        dict: {"next_status": str, "approver": str or None, "approver_email": str or None}
    """
    flow = STATUS_FLOWS.get(category, STATUS_FLOWS["other"])
    
    for step in flow:
        if step["status"] == current_status:
            approver_key = step.get("approver")
            approver_email = APPROVERS.get(approver_key) if approver_key else None
            
            return {
                "next_status": step["next_status"],
                "approver": approver_key,
                "approver_email": approver_email
            }
    
    return None


@frappe.whitelist()
def get_approver_for_employee(employee_name):
    """
    API method to get the initial approver and status for a given employee.
    Called from client-side when employee is selected.
    
    Args:
        employee_name: Name of the employee
        
    Returns:
        dict: {
            "leave_approver": email of the approver,
            "leave_approver_name": name of the approver,
            "custom_approval_status": initial approval status,
            "approver_role": HOD/HR/GM
        }
    """
    if not employee_name:
        return None
    
    role_profile = get_employee_role_profile(employee_name)
    category = get_employee_category(role_profile, employee_name)
    
    initial_config = INITIAL_CONFIG.get(category, INITIAL_CONFIG["other"])
    
    approver_key = initial_config["approver"]
    approver_email = APPROVERS.get(approver_key, "")
    approver_name = frappe.db.get_value("User", approver_email, "full_name") if approver_email else approver_key
    
    return {
        "leave_approver": approver_email,
        "leave_approver_name": approver_name or approver_key,
        "custom_approval_status": initial_config["status"],
        "approver_role": approver_key
    }


def set_leave_approver(doc, method):
    """
    Set initial leave approver and custom_approval_status based on employee category.
    Called on before_save/validate of Leave Application.
    """
    # Only set on new documents that don't have custom_approval_status already set
    # This prevents resetting the status when approver saves the document
    if doc.is_new() and not doc.custom_approval_status:
        employee_name = doc.employee_name
        role_profile = get_employee_role_profile(employee_name)
        category = get_employee_category(role_profile, employee_name)
        
        initial_config = INITIAL_CONFIG.get(category, INITIAL_CONFIG["other"])
        
        # Set initial custom_approval_status
        doc.custom_approval_status = initial_config["status"]
        
        # Set initial approver
        approver_key = initial_config["approver"]
        if approver_key and approver_key in APPROVERS:
            doc.leave_approver = APPROVERS[approver_key]
            # Set leave approver name
            approver_user = frappe.db.get_value("User", doc.leave_approver, "full_name")
            doc.leave_approver_name = approver_user or approver_key
        
        frappe.msgprint(
            _("Leave Application routed to {0} for approval").format(approver_key),
            indicator="blue",
            alert=True
        )


def on_approval_update(doc, method):
    """
    Handle status transitions when leave application is approved.
    Called on on_update of Leave Application.
    
    When the current approver approves (changes custom_approval_status to Approved X),
    this function sets the next approver and updates the status accordingly.
    """
    # Get custom_approval_status, return if not set
    if not doc.custom_approval_status:
        return
    
    # Skip if document is being cancelled or rejected
    if doc.status in ["Cancelled", "Rejected"]:
        return
    
    # Skip if already fully approved
    if doc.custom_approval_status == "Approved":
        # Also set the standard status to Approved
        if doc.status != "Approved":
            doc.db_set("status", "Approved")
        return
    
    employee_name = doc.employee_name
    role_profile = get_employee_role_profile(employee_name)
    category = get_employee_category(role_profile, employee_name)
    
    current_status = doc.custom_approval_status
    
    # Check if current status is an "Approved" intermediate status
    # that needs to transition to next "Pending" status
    if current_status.startswith("Approved") and current_status != "Approved":
        next_info = get_next_approver_and_status(category, current_status)
        
        if next_info:
            # Update custom_approval_status to next pending status
            doc.db_set("custom_approval_status", next_info["next_status"])
            
            # Set next approver if exists
            if next_info["approver_email"]:
                doc.db_set("leave_approver", next_info["approver_email"])
                approver_name = frappe.db.get_value("User", next_info["approver_email"], "full_name")
                doc.db_set("leave_approver_name", approver_name or next_info["approver"])
                
                frappe.msgprint(
                    _("Leave Application forwarded to {0} for approval").format(next_info["approver"]),
                    indicator="blue",
                    alert=True
                )
            
            # If final approval, set the standard status to Approved
            if next_info["next_status"] == "Approved":
                doc.db_set("status", "Approved")


@frappe.whitelist()
def approve_leave(doc_name, approval_action="approve"):
    """
    API method to approve a leave application.
    This moves the leave application to the next pending status in the approval chain.
    Uses db_set to directly update database, bypassing all permission checks.
    
    Args:
        doc_name: Name of the Leave Application document
        approval_action: "approve" or "reject"
    """
    doc = frappe.get_doc("Leave Application", doc_name)
    
    # Verify current user is the designated approver
    current_user = frappe.session.user
    if doc.leave_approver and current_user != doc.leave_approver and current_user != "Administrator":
        frappe.throw(_("Only the designated approver ({0}) can approve this leave application").format(doc.leave_approver))
    
    if approval_action == "reject":
        # Use db_set to bypass all permissions
        frappe.db.set_value("Leave Application", doc_name, {
            "status": "Rejected",
            "custom_approval_status": "Rejected"
        }, update_modified=True)
        frappe.db.commit()
        frappe.msgprint(_("Leave Application rejected"), indicator="red")
        return {"success": True, "message": "Leave Application rejected"}
    
    employee_name = doc.employee_name
    role_profile = get_employee_role_profile(employee_name)
    category = get_employee_category(role_profile, employee_name)
    
    current_status = doc.custom_approval_status
    
    # Get the flow for this category
    flow = STATUS_FLOWS.get(category, STATUS_FLOWS["other"])
    
    # Find current step
    current_step = None
    current_step_index = None
    for i, step in enumerate(flow):
        if step["status"] == current_status:
            current_step = step
            current_step_index = i
            break
    
    if current_step is None:
        frappe.throw(_("Invalid status transition from {0}").format(current_status))
    
    # Get the approved status (what happens after current approver approves)
    approved_status = current_step["next_status"]  # e.g., "Approved HR" or "Approved GM"
    is_final = current_step.get("is_final", False)
    
    if is_final:
        # This is the final approval step
        # Set HRMS status to "Approved" (for leave deduction)
        # But keep custom_approval_status as "Approved GM" or "Approved HR"
        frappe.db.set_value("Leave Application", doc_name, {
            "status": "Approved",
            "custom_approval_status": approved_status  # e.g., "Approved GM" or "Approved HR"
        }, update_modified=True)
        frappe.db.commit()
        frappe.msgprint(_("Leave Application fully approved"), indicator="green")
        return {"success": True, "message": "Leave Application fully approved", "new_status": approved_status}
    else:
        # Not final - find the next step to get the next approver
        next_pending_status = None
        next_approver_key = None
        
        # Find the next "Pending X" status after this approval
        for j in range(current_step_index + 1, len(flow)):
            next_step = flow[j]
            if next_step["status"] == approved_status:
                # This step handles the transition from "Approved X" to next
                next_pending_status = next_step["next_status"]
                break
        
        # Find the approver for the next pending status
        if next_pending_status and next_pending_status.startswith("Pending"):
            for step in flow:
                if step["status"] == next_pending_status:
                    next_approver_key = step.get("approver")
                    break
        
        # Update the leave application
        update_values = {
            "custom_approval_status": approved_status  # e.g., "Approved HR"
        }
        
        # Set the next approver
        if next_approver_key and next_approver_key in APPROVERS:
            update_values["leave_approver"] = APPROVERS[next_approver_key]
            approver_name = frappe.db.get_value("User", APPROVERS[next_approver_key], "full_name")
            update_values["leave_approver_name"] = approver_name or next_approver_key
        
        frappe.db.set_value("Leave Application", doc_name, update_values, update_modified=True)
        frappe.db.commit()
        
        frappe.msgprint(
            _("Leave Application approved. Forwarded to {0}").format(next_approver_key or "next approver"),
            indicator="blue"
        )
        return {"success": True, "message": f"Forwarded to {next_approver_key or 'next approver'}", "new_status": approved_status}


def on_hrms_submit(doc, method):
    """
    Handle when HRMS submits/approves the leave application using its standard workflow.
    This ensures our custom_approval_status stays in sync.
    """
    # When HRMS submits/approves directly, update our custom_approval_status
    if doc.status == "Approved" and doc.custom_approval_status != "Approved":
        # HRMS approved directly, set our status to Approved
        doc.db_set("custom_approval_status", "Approved", update_modified=False)


def on_hrms_status_change(doc, method):
    """
    Handle when HRMS changes the status of a submitted leave application.
    This captures the standard HRMS Approve/Reject button clicks.
    """
    # If the standard status changed to Approved
    if doc.status == "Approved" and doc.custom_approval_status and doc.custom_approval_status.startswith("Pending"):
        # HRMS approved, so we need to transition our custom status
        employee_name = doc.employee_name
        role_profile = get_employee_role_profile(employee_name)
        category = get_employee_category(role_profile, employee_name)
        
        current_status = doc.custom_approval_status
        
        # Get the flow for this category
        flow = STATUS_FLOWS.get(category, STATUS_FLOWS["other"])
        
        # Find the next pending status or Approved
        next_pending_status = None
        next_approver_key = None
        
        # Find current step index
        current_step_index = None
        for i, step in enumerate(flow):
            if step["status"] == current_status:
                current_step_index = i
                break
        
        if current_step_index is not None:
            # Move to next "Pending" status or "Approved"
            for j in range(current_step_index, len(flow)):
                step = flow[j]
                next_status = step["next_status"]
                
                if next_status == "Approved":
                    next_pending_status = "Approved"
                    break
                elif next_status.startswith("Pending"):
                    next_pending_status = next_status
                    # Find the approver for this pending status
                    for k in range(j + 1, len(flow)):
                        if flow[k]["status"] == next_status:
                            next_approver_key = flow[k].get("approver")
                            break
                    break
        
        if next_pending_status:
            doc.db_set("custom_approval_status", next_pending_status, update_modified=False)
            
            # Set next approver if not final
            if next_pending_status != "Approved" and next_approver_key and next_approver_key in APPROVERS:
                doc.db_set("leave_approver", APPROVERS[next_approver_key], update_modified=False)
                approver_name = frappe.db.get_value("User", APPROVERS[next_approver_key], "full_name")
                doc.db_set("leave_approver_name", approver_name or next_approver_key, update_modified=False)
    
    # If the standard status changed to Rejected
    elif doc.status == "Rejected" and doc.custom_approval_status != "Rejected":
        doc.db_set("custom_approval_status", "Rejected", update_modified=False)
