import frappe
from frappe import _

# Approver configuration - Email addresses for each approver role
APPROVERS = {
    "HOD": "chundakadannorthasm@gmail.com",
    "HR": "binduudayan334@gmail.com",
    "GM": "chundakadangm@gmail.com"
}

# Status flow definitions for each employee category
STATUS_FLOWS = {
    "sales_executive": [
        {"status": "Pending HOD", "next_status": "Approved HOD", "approver": "HOD"},
        {"status": "Approved HOD", "next_status": "Pending HR", "approver": None},
        {"status": "Pending HR", "next_status": "Approved HR", "approver": "HR"},
        {"status": "Approved HR", "next_status": "Pending GM", "approver": None},
        {"status": "Pending GM", "next_status": "Approved GM", "approver": "GM"},
        {"status": "Approved GM", "next_status": "Approved", "approver": None},
    ],
    "other": [
        {"status": "Pending HR", "next_status": "Approved HR", "approver": "HR"},
        {"status": "Approved HR", "next_status": "Pending GM", "approver": None},
        {"status": "Pending GM", "next_status": "Approved GM", "approver": "GM"},
        {"status": "Approved GM", "next_status": "Approved", "approver": None},
    ],
    "hod_hr": [
        {"status": "Pending GM", "next_status": "Approved GM", "approver": "GM"},
        {"status": "Approved GM", "next_status": "Approved", "approver": None},
    ],
    "gm": [
        {"status": "Pending HR", "next_status": "Approved HR", "approver": "HR"},
        {"status": "Approved HR", "next_status": "Approved", "approver": None},
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
    # Only set on new documents or when status is Open
    if doc.is_new() or doc.status == "Open":
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
    This moves the leave application to the next status in the approval chain.
    
    Args:
        doc_name: Name of the Leave Application document
        approval_action: "approve" or "reject"
    """
    doc = frappe.get_doc("Leave Application", doc_name)
    
    if approval_action == "reject":
        doc.status = "Rejected"
        doc.custom_approval_status = "Rejected"
        doc.save()
        frappe.msgprint(_("Leave Application rejected"), indicator="red")
        return {"success": True, "message": "Leave Application rejected"}
    
    employee_name = doc.employee_name
    role_profile = get_employee_role_profile(employee_name)
    category = get_employee_category(role_profile, employee_name)
    
    current_status = doc.custom_approval_status
    
    # Find the current step in the flow and move to next
    next_info = get_next_approver_and_status(category, current_status)
    
    if next_info:
        doc.custom_approval_status = next_info["next_status"]
        
        # If next status is another pending status, set the approver
        if next_info["approver_email"]:
            doc.leave_approver = next_info["approver_email"]
            approver_name = frappe.db.get_value("User", next_info["approver_email"], "full_name")
            doc.leave_approver_name = approver_name or next_info["approver"]
        
        # If final approval, set the standard status to Approved
        if next_info["next_status"] == "Approved":
            doc.status = "Approved"
        
        doc.save()
        
        if doc.custom_approval_status == "Approved":
            frappe.msgprint(_("Leave Application fully approved"), indicator="green")
            return {"success": True, "message": "Leave Application fully approved"}
        else:
            frappe.msgprint(
                _("Leave Application approved. Forwarded to {0}").format(next_info.get("approver", "next approver")),
                indicator="blue"
            )
            return {"success": True, "message": f"Forwarded to {next_info.get('approver', 'next approver')}"}
    else:
        frappe.throw(_("Invalid status transition"))
