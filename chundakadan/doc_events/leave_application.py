import frappe
from frappe import _
#code written by niranjana nir

# Approver configuration - Email addresses for each approver role
APPROVERS = {
    "HOD": "chundakadannorthasm@gmail.com",
    "HR": "binduudayan334@gmail.com",
    "GM": "chundakadangm@gmail.com"
}

# Status flow definitions for each employee category
# Each step defines the current custom_approval_status and what it transitions to
# approver=None means it's a transition step (e.g. Approved HOD -> Pending HR)
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


def get_employee_role_profile(employee_name, employee=None):
    """
    Get role_profile_name from User linked to employee.
    First tries to match by linked User field in Employee,
    then by full_name, then by User docname.
    """
    if not employee_name and not employee:
        return None

    # Try matching with linked User field in Employee first
    if employee:
        user_id = frappe.db.get_value("Employee", employee, "user_id")
        if user_id:
            role_profile = frappe.db.get_value("User", user_id, "role_profile_name")
            if role_profile:
                return role_profile
    
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


def get_employee_category(role_profile, employee_name=None, employee=None):
    """
    Determine employee category based on Employee designation or role profile name.
    
    Categories:
    - sales_executive: For Sales Executive designation or role profile
    - hod_hr: For Coordinator (HR) or Area Sales Manager (HOD) designations, or HOD/HR role profiles
    - gm: For General Manager designation or GM role profile
    - other: All other role profiles
    """
    # Fetch Employee data for designation check
    emp_data = None
    if employee or employee_name:
        emp_filters = {"name": employee} if employee else {"employee_name": employee_name}
        emp_data = frappe.db.get_value("Employee", emp_filters, ["designation", "employee_name"], as_dict=True)

    if emp_data:
        designation = emp_data.designation
        
        # 1. Check for GM (General Manager)
        if designation == "General Manager":
            return "gm"
        
        # 2. Check for HR (Coordinator / HR Coordinator)
        # Leaves go directly to GM for approval
        if designation in ["Coordinator", "HR Coordinator"]:
            return "hod_hr"

        # 3. Check for HOD (Area Sales Manager)
        # Leaves go to HR first, then GM
        if designation == "Area Sales Manager":
            return "other"
            
        # 4. Check for Sales Executive
        # Leaves go to HOD -> HR -> GM
        if designation == "Sales Executive":
            # As requested, also verify employee_name matches
            if not employee_name or emp_data.employee_name == employee_name:
                return "sales_executive"

    # Special case: Bindu T should be treated as HR (hod_hr category)
    # Her leaves should go directly to GM for approval
    if employee_name and employee_name.strip().lower() == "bindu t":
        return "hod_hr"
    
    # Special case: Najeeb Sulaiman (GM) should be treated as gm category
    # His leaves should only go to HR for approval
    if employee_name and ("najeeb" in employee_name.lower() and "sulaiman" in employee_name.lower()):
        return "gm"
    
    if not role_profile:
        return "other"
    
    role_profile_lower = role_profile.lower().strip()
    
    # Check for Sales Executive (partial match from role profile)
    if "sales executive" in role_profile_lower or role_profile_lower == "sales executive":
        return "sales_executive"
    
    # Check for GM / General Manager (partial match)
    if role_profile_lower == "gm" or "general manager" in role_profile_lower:
        return "gm"
    
    # Check for HOD (partial match)
    if role_profile_lower == "hod" or "head of department" in role_profile_lower:
        return "hod_hr"
    
    # Check for HR (partial match)
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
def get_approver_for_employee(employee_name, employee=None):
    """
    API method to get the initial approver and status for a given employee.
    Called from client-side when employee is selected.
    
    Args:
        employee_name: Name of the employee
        employee: Employee ID (optional but recommended)
        
    Returns:
        dict: {
            "leave_approver": email of the approver,
            "leave_approver_name": name of the approver,
            "custom_approval_status": initial approval status,
            "approver_role": HOD/HR/GM
        }
    """
    if not employee_name and not employee:
        return None
    
    role_profile = get_employee_role_profile(employee_name, employee)
    category = get_employee_category(role_profile, employee_name, employee)
    
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
        employee = doc.employee
        role_profile = get_employee_role_profile(employee_name, employee)
        category = get_employee_category(role_profile, employee_name, employee)
        
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
    
    NOTE: Auto-transition from "Approved X" intermediate statuses is DISABLED.
    The next approver (e.g., GM) must manually click approve to transition
    from "Approved HR" to "Pending GM" and then to "Approved GM".
    This ensures everyone sees the actual stored status at each step.
    """
    # Skip if being called from approve_leave (to avoid duplicate processing)
    if getattr(doc.flags, 'skip_approval_update', False):
        return
    
    # Get custom_approval_status, return if not set
    if not doc.custom_approval_status:
        return
    
    # Skip if document is being cancelled or rejected
    if doc.status in ["Cancelled", "Rejected"]:
        return
    
    # Skip if already fully approved (HRMS status is Approved or document is submitted)
    if doc.custom_approval_status == "Approved" or doc.status == "Approved" or doc.docstatus == 1:
        return
    
    # NOTE: Auto-transition from intermediate "Approved X" statuses is DISABLED
    # The GM must manually click approve to transition:
    # 1. First click: "Approved HR" -> "Pending GM"
    # 2. Second click: "Pending GM" -> "Approved GM"
    # This ensures all users see the correct status at each stage.
    # The approve_leave() function handles the manual transitions.


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
    employee = doc.employee
    role_profile = get_employee_role_profile(employee_name, employee)
    category = get_employee_category(role_profile, employee_name, employee)
    
    current_status = doc.custom_approval_status
    
    # Fallback for generic "Pending" status (default value in database)
    if current_status == "Pending":
        initial_config = INITIAL_CONFIG.get(category, INITIAL_CONFIG["other"])
        current_status = initial_config["status"]
    
    # Get the flow for this category
    flow = STATUS_FLOWS.get(category, STATUS_FLOWS["other"])
    
    # Find current step - handle both "Pending X" and "Approved X" (intermediate) statuses
    current_step = None
    current_step_index = None
    is_transition_step = False  # Flag to indicate if this is a transition step (Approved X -> Pending X)
    
    for i, step in enumerate(flow):
        if step["status"] == current_status:
            current_step = step
            current_step_index = i
            break
    
    # If current status is intermediate "Approved X" (transition step with approver=None),
    # this means we need to transition to the next "Pending X" status
    # This is NOT the final approval - GM needs to click again on "Pending GM" for final
    if current_step and current_step.get("approver") is None and current_status.startswith("Approved"):
        # This is a transition step - mark it so we handle it correctly below
        is_transition_step = True
    elif current_step is None and current_status.startswith("Approved"):
        # Fallback: status is "Approved X" but not found - try to find it
        for i, step in enumerate(flow):
            if step["status"] == current_status:
                current_step = step
                current_step_index = i
                is_transition_step = True
                break
    
    if current_step is None:
        frappe.throw(_("Invalid status transition from {0}").format(doc.custom_approval_status))
    
    # Get the next status from current step
    next_status = current_step["next_status"]  # e.g., "Pending GM" for transition or "Approved GM" for approval
    is_final = current_step.get("is_final", False)
    
    # Handle transition step (Approved X -> Pending X)
    # This is when GM clicks approve on "Approved HR" - it should change to "Pending GM"
    if is_transition_step:
        # Just transition to the next pending status
        next_pending_status = next_status  # e.g., "Pending GM"
        
        # Find the approver for the next pending status
        next_approver_key = None
        for step in flow:
            if step["status"] == next_pending_status:
                next_approver_key = step.get("approver")
                break
        
        update_values = {
            "custom_approval_status": next_pending_status
        }
        
        # Set the approver (same user for GM since they're the next approver)
        if next_approver_key and next_approver_key in APPROVERS:
            update_values["leave_approver"] = APPROVERS[next_approver_key]
            approver_name = frappe.db.get_value("User", APPROVERS[next_approver_key], "full_name")
            update_values["leave_approver_name"] = approver_name or next_approver_key
        
        frappe.db.set_value("Leave Application", doc_name, update_values, update_modified=True)
        frappe.db.commit()
        
        frappe.msgprint(
            _("Status updated to {0}. Click Approve again to complete approval.").format(next_pending_status),
            indicator="blue"
        )
        return {"success": True, "message": f"Status updated to {next_pending_status}", "new_status": next_pending_status}
    
    if is_final:
        # This is the final approval step
        # Set custom_approval_status and status to "Approved", then submit the document
        # Submitting will trigger HRMS to create Leave Ledger Entry and update leave balance
        
        # First update the custom_approval_status and status in database
        frappe.db.set_value("Leave Application", doc_name, {
            "custom_approval_status": next_status,  # e.g., "Approved GM" or "Approved HR"
            "status": "Approved"
        }, update_modified=True)
        frappe.db.commit()
        
        # Reload the document with updated values
        doc.reload()
        
        # Ensure status is "Approved" in memory (in case validate hooks try to change it)
        doc.status = "Approved"
        doc.flags.ignore_permissions = True
        doc.flags.ignore_validate = True  # Skip validation that might reset status
        doc.flags.skip_approval_update = True  # Skip on_approval_update hook to avoid duplicate messages
        
        # Submit the document - this sets docstatus to 1
        # HRMS on_submit hook will call create_leave_ledger_entry()
        doc.submit()
        
        # Ensure status is still "Approved" after submit
        if doc.status != "Approved":
            frappe.db.set_value("Leave Application", doc_name, "status", "Approved", update_modified=False)
            frappe.db.commit()
        
        # Verify leave ledger entry was created, if not create it manually
        leave_ledger_exists = frappe.db.exists(
            "Leave Ledger Entry",
            {
                "transaction_type": "Leave Application",
                "transaction_name": doc_name,
                "docstatus": 1
            }
        )
        
        if not leave_ledger_exists:
            # Leave ledger entry was not created, create it manually
            doc.reload()
            doc.status = "Approved"  # Ensure status is Approved for ledger creation
            doc.create_leave_ledger_entry()
        
        frappe.msgprint(_("Leave Application fully approved"), indicator="green")
        return {"success": True, "message": "Leave Application fully approved", "new_status": next_status}
    else:
        # Not final - find the next step to get the next approver
        approved_status = next_status  # e.g., "Approved HR"
        next_pending_status = None
        next_approver_key = None
        
        # Find the next "Pending X" status after this approval
        for j in range(current_step_index + 1, len(flow)):
            next_step = flow[j]
            if next_step["status"] == approved_status:
                # This step handles the transition from "Approved X" to next "Pending X"
                next_pending_status = next_step["next_status"]
                break
        
        # Find the approver for the next pending status
        if next_pending_status and next_pending_status.startswith("Pending"):
            for step in flow:
                if step["status"] == next_pending_status:
                    next_approver_key = step.get("approver")
                    break
        
        # Update the leave application - store the approved status (e.g., "Approved HR")
        # Everyone sees "Approved HR", GM will see it and click approve to transition
        update_values = {
            "custom_approval_status": approved_status  # Store "Approved HR"
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
    # When HRMS submits/approves directly (not through our custom approve_leave function),
    # update our custom_approval_status. But preserve existing "Approved X" values.
    if doc.status == "Approved":
        # Don't overwrite if already has a proper final approval status like "Approved GM" or "Approved HR"
        if doc.custom_approval_status and doc.custom_approval_status.startswith("Approved "):
            # Already has a proper approval status (e.g., "Approved GM"), keep it
            pass
        elif doc.custom_approval_status != "Approved":
            # HRMS approved directly without going through our flow, set to generic Approved
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
        employee = doc.employee
        role_profile = get_employee_role_profile(employee_name, employee)
        category = get_employee_category(role_profile, employee_name, employee)
        
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
