import frappe
from frappe import _
#code written by niranjana nir

# Designation-to-approver-role mapping
# Maps each approver role to the designation used to find the approver employee
# HR uses a list to support both "HR Coordinator" and "Coordinator" designations
APPROVER_DESIGNATIONS = {
    "HOD": "Area Sales Manager",
    "HR": ["HR Coordinator", "Coordinator"],
    "GM": "General Manager"
}

# Fallback email addresses (used only if no active employee with the designation is found)
FALLBACK_APPROVER_EMAILS = {
    "HOD": "chundakadannorthasm@gmail.com",
    "HR": "binduudayan334@gmail.com",
    "GM": "chundakadangm@gmail.com"
}

# Cache for approver lookups (cleared on each request)
_approver_cache = {}


def get_approver_email(approver_key):
    """
    Dynamically find the approver's email (user_id) based on their designation.
    
    Looks up an active Employee with the matching designation and returns their user_id.
    Falls back to hardcoded email if no employee is found.
    
    Args:
        approver_key: One of "HOD", "HR", "GM"
        
    Returns:
        str: Email address (user_id) of the approver
    """
    global _approver_cache
    
    if approver_key in _approver_cache:
        return _approver_cache[approver_key]
    
    designation = APPROVER_DESIGNATIONS.get(approver_key)
    if not designation:
        return FALLBACK_APPROVER_EMAILS.get(approver_key, "")
    
    # Support list of designations (e.g., HR can be "HR Coordinator" or "Coordinator")
    designations = designation if isinstance(designation, list) else [designation]
    
    for desig in designations:
        # Find an active employee with this designation who has a linked user_id
        employee = frappe.db.get_value(
            "Employee",
            {
                "designation": desig,
                "status": "Active",
                "user_id": ["is", "set"]
            },
            ["user_id", "employee_name"],
            as_dict=True
        )
        
        if employee and employee.user_id:
            _approver_cache[approver_key] = employee.user_id
            return employee.user_id
        
        # Try without status filter (in case employee status differs)
        employee = frappe.db.get_value(
            "Employee",
            {
                "designation": desig,
                "user_id": ["is", "set"]
            },
            ["user_id", "employee_name"],
            as_dict=True
        )
        
        if employee and employee.user_id:
            _approver_cache[approver_key] = employee.user_id
            return employee.user_id
    
    # Final fallback to hardcoded email
    fallback = FALLBACK_APPROVER_EMAILS.get(approver_key, "")
    _approver_cache[approver_key] = fallback
    return fallback


def clear_approver_cache():
    """Clear the approver cache. Called at the start of key operations."""
    global _approver_cache
    _approver_cache = {}


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
            approver_email = get_approver_email(approver_key) if approver_key else None
            
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
    
    # Clear cache to ensure fresh lookup
    clear_approver_cache()
    
    role_profile = get_employee_role_profile(employee_name, employee)
    category = get_employee_category(role_profile, employee_name, employee)
    
    initial_config = INITIAL_CONFIG.get(category, INITIAL_CONFIG["other"])
    
    approver_key = initial_config["approver"]
    approver_email = get_approver_email(approver_key)
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
        # Clear cache to ensure fresh lookup
        clear_approver_cache()
        
        employee_name = doc.employee_name
        employee = doc.employee
        role_profile = get_employee_role_profile(employee_name, employee)
        category = get_employee_category(role_profile, employee_name, employee)
        
        initial_config = INITIAL_CONFIG.get(category, INITIAL_CONFIG["other"])
        
        # Set initial custom_approval_status
        doc.custom_approval_status = initial_config["status"]
        
        # Set initial approver
        approver_key = initial_config["approver"]
        approver_email = get_approver_email(approver_key)
        if approver_email:
            doc.leave_approver = approver_email
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
    # Clear cache to ensure fresh lookup
    clear_approver_cache()
    
    doc = frappe.get_doc("Leave Application", doc_name)
    
    # Verify current user is the designated approver (by email or by designation)
    current_user = frappe.session.user
    is_authorized = False
    
    if current_user == "Administrator":
        is_authorized = True
    elif doc.leave_approver and current_user == doc.leave_approver:
        is_authorized = True
    else:
        # Fallback: check if user's Employee designation matches the required approver role
        required_designation = _get_required_designation_for_status(doc.custom_approval_status)
        if required_designation and _user_has_approver_designation(current_user, required_designation):
            is_authorized = True
            # Update leave_approver to current user so it's consistent
            frappe.db.set_value("Leave Application", doc_name, "leave_approver", current_user, update_modified=False)
            approver_name = frappe.db.get_value("User", current_user, "full_name")
            if approver_name:
                frappe.db.set_value("Leave Application", doc_name, "leave_approver_name", approver_name, update_modified=False)
            doc.leave_approver = current_user
    
    if not is_authorized:
        frappe.throw(_(
            "Only the designated approver ({0}) can approve this leave application"
        ).format(doc.leave_approver))
    
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
    is_transition_step = False  # Flag: "Approved X" -> "Pending X" transition
    
    for i, step in enumerate(flow):
        if step["status"] == current_status:
            current_step = step
            current_step_index = i
            break
    
    # If current status is intermediate "Approved X" (transition step with approver=None),
    # this means we need to transition to the next "Pending X" status
    if current_step and current_step.get("approver") is None and current_status.startswith("Approved"):
        is_transition_step = True
    elif current_step is None and current_status.startswith("Approved"):
        # Fallback: status is "Approved X" but not found in flow
        for i, step in enumerate(flow):
            if step["status"] == current_status:
                current_step = step
                current_step_index = i
                is_transition_step = True
                break
    
    if current_step is None:
        frappe.throw(_("Invalid status transition from {0}").format(doc.custom_approval_status))
    
    next_status = current_step["next_status"]
    is_final = current_step.get("is_final", False)
    
    # Handle transition step (e.g., "Approved HR" -> "Pending GM")
    # GM clicks approve on "Approved HR" to change it to "Pending GM"
    if is_transition_step:
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
        
        if next_approver_key:
            next_approver_email = get_approver_email(next_approver_key)
            if next_approver_email:
                update_values["leave_approver"] = next_approver_email
                approver_name = frappe.db.get_value("User", next_approver_email, "full_name")
                update_values["leave_approver_name"] = approver_name or next_approver_key
        
        frappe.db.set_value("Leave Application", doc_name, update_values, update_modified=True)
        frappe.db.commit()
        
        frappe.msgprint(
            _("Status updated to {0}. Click Approve again to complete approval.").format(next_pending_status),
            indicator="blue"
        )
        return {"success": True, "message": f"Status updated to {next_pending_status}", "new_status": next_pending_status}
    
    if is_final:
        # Final approval step - submit the document
        frappe.db.set_value("Leave Application", doc_name, {
            "custom_approval_status": next_status,  # e.g., "Approved GM"
            "status": "Approved"
        }, update_modified=True)
        frappe.db.commit()
        
        doc.reload()
        doc.status = "Approved"
        doc.flags.ignore_permissions = True
        doc.flags.ignore_validate = True
        doc.flags.skip_approval_update = True
        doc.submit()
        
        if doc.status != "Approved":
            frappe.db.set_value("Leave Application", doc_name, "status", "Approved", update_modified=False)
            frappe.db.commit()
        
        # Verify leave ledger entry was created
        leave_ledger_exists = frappe.db.exists(
            "Leave Ledger Entry",
            {
                "transaction_type": "Leave Application",
                "transaction_name": doc_name,
                "docstatus": 1
            }
        )
        
        if not leave_ledger_exists:
            doc.reload()
            doc.status = "Approved"
            doc.create_leave_ledger_entry()
        
        frappe.msgprint(_("Leave Application fully approved"), indicator="green")
        return {"success": True, "message": "Leave Application fully approved", "new_status": next_status}
    else:
        # Not final - store "Approved X" and set next approver
        approved_status = next_status  # e.g., "Approved HOD" or "Approved HR"
        next_pending_status = None
        next_approver_key = None
        
        # Find the next "Pending X" status after this approval
        for j in range(current_step_index + 1, len(flow)):
            next_step = flow[j]
            if next_step["status"] == approved_status:
                next_pending_status = next_step["next_status"]
                break
        
        # Find the approver for the next pending status
        if next_pending_status and next_pending_status.startswith("Pending"):
            for step in flow:
                if step["status"] == next_pending_status:
                    next_approver_key = step.get("approver")
                    break
        
        update_values = {
            "custom_approval_status": approved_status  # Store "Approved HR"
        }
        
        # Set the next approver (the person who needs to handle the transition click)
        if next_approver_key:
            next_approver_email = get_approver_email(next_approver_key)
            if next_approver_email:
                update_values["leave_approver"] = next_approver_email
                approver_name = frappe.db.get_value("User", next_approver_email, "full_name")
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
    # Clear cache to ensure fresh lookup
    clear_approver_cache()
    
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
            if next_pending_status != "Approved" and next_approver_key:
                next_approver_email = get_approver_email(next_approver_key)
                if next_approver_email:
                    doc.db_set("leave_approver", next_approver_email, update_modified=False)
                    approver_name = frappe.db.get_value("User", next_approver_email, "full_name")
                    doc.db_set("leave_approver_name", approver_name or next_approver_key, update_modified=False)
    
    # If the standard status changed to Rejected
    elif doc.status == "Rejected" and doc.custom_approval_status != "Rejected":
        doc.db_set("custom_approval_status", "Rejected", update_modified=False)


def _get_required_designation_for_status(status):
    """
    Given a custom_approval_status, return the designation(s) required to approve it.
    Returns a list of acceptable designations to support multiple designations per role.
    E.g., "Pending HOD" -> ["Area Sales Manager"], "Pending HR" -> ["HR Coordinator", "Coordinator"]
    """
    status_to_role = {
        "Pending HOD": "HOD",
        "Pending HR": "HR",
        "Pending GM": "GM",
        # Intermediate approved statuses - next approver handles transition click
        "Approved HOD": "HR",   # HR clicks to move from Approved HOD -> Pending HR
        "Approved HR": "GM",    # GM clicks to move from Approved HR -> Pending GM
    }
    role = status_to_role.get(status)
    if role:
        desig = APPROVER_DESIGNATIONS.get(role)
        if desig:
            return desig if isinstance(desig, list) else [desig]
    return []


def _user_has_approver_designation(user, required_designations):
    """
    Check if the given user is linked to an Employee with one of the required designations.
    
    Args:
        user: User email
        required_designations: A string or list of acceptable designations
    """
    if not user or not required_designations:
        return False
    
    # Normalize to list
    if isinstance(required_designations, str):
        required_designations = [required_designations]
    
    for designation in required_designations:
        employee = frappe.db.get_value(
            "Employee",
            {"user_id": user, "designation": designation},
            "name"
        )
        if employee:
            return True
    return False


@frappe.whitelist()
def check_user_can_approve(doc_name, user=None):
    """
    Check if the given user can approve the specified leave application.
    
    This function validates if the user has the authority to approve based on 
    their designation and the current approval status. It ensures that once 
    a user has approved their stage (e.g. HOD approved), they no longer see 
    the approval buttons.
    """
    if not user:
        user = frappe.session.user
    
    if user == "Administrator":
        return {"can_approve": True, "reason": "Administrator"}
    
    doc = frappe.get_doc("Leave Application", doc_name)
    status = doc.custom_approval_status
    hrms_status = doc.status
    
    # Don't allow if already fully approved or document is submitted
    if hrms_status == "Approved" or doc.docstatus == 1:
        return {"can_approve": False, "reason": "Already approved"}
    
    if not status:
        return {"can_approve": False, "reason": "No approval status set"}
    
    # Get required designation for current status
    required_designation = _get_required_designation_for_status(status)
    
    # Authoritative check: Does the user's designation match the requirement?
    if required_designation and _user_has_approver_designation(user, required_designation):
        # User is eligible to approve this stage. 
        # Update leave_approver field if it doesn't match to ensure consistent UI
        if user != doc.leave_approver:
            try:
                frappe.db.set_value(
                    "Leave Application", doc_name, "leave_approver", user,
                    update_modified=False
                )
                approver_name = frappe.db.get_value("User", user, "full_name")
                if approver_name:
                    frappe.db.set_value(
                        "Leave Application", doc_name, "leave_approver_name", approver_name,
                        update_modified=False
                    )
                frappe.db.commit()
            except Exception:
                pass
        return {"can_approve": True, "reason": f"Designation match: {required_designation}"}
    
    # If designation requirement exists but user doesn't match, deny
    if required_designation:
        return {"can_approve": False, "reason": f"Required designation: {required_designation}"}

    # Fallback for statuses without specific designation requirements
    if user == doc.leave_approver:
        return {"can_approve": True, "reason": "Designated approver"}
    
    return {"can_approve": False, "reason": "No matching designation"}


@frappe.whitelist()
def diagnose_leave_approval(doc_name=None):
    """
    Diagnostic API to debug leave approval issues in production.
    Returns detailed information about the approval setup.
    
    Args:
        doc_name: Optional Leave Application name to diagnose
        
    Returns:
        dict: Diagnostic information
    """
    clear_approver_cache()
    current_user = frappe.session.user
    
    result = {
        "current_user": current_user,
        "approver_lookup": {},
        "current_user_employee": None,
        "doc_info": None
    }
    
    # Check approver lookups
    for role, designation in APPROVER_DESIGNATIONS.items():
        email = get_approver_email(role)
        # Handle list of designations (e.g., HR can be "HR Coordinator" or "Coordinator")
        designations = designation if isinstance(designation, list) else [designation]
        emp = None
        for desig in designations:
            emp = frappe.db.get_value(
                "Employee",
                {"designation": desig, "user_id": ["is", "set"]},
                ["name", "employee_name", "user_id", "designation", "status"],
                as_dict=True
            )
            if emp:
                break
        result["approver_lookup"][role] = {
            "designation": designation,
            "resolved_email": email,
            "fallback_email": FALLBACK_APPROVER_EMAILS.get(role),
            "employee": emp
        }
    
    # Check current user's employee
    emp = frappe.db.get_value(
        "Employee",
        {"user_id": current_user},
        ["name", "employee_name", "designation", "status"],
        as_dict=True
    )
    result["current_user_employee"] = emp
    
    # If doc_name provided, check the specific document
    if doc_name:
        doc = frappe.get_doc("Leave Application", doc_name)
        role_profile = get_employee_role_profile(doc.employee_name, doc.employee)
        category = get_employee_category(role_profile, doc.employee_name, doc.employee)
        
        result["doc_info"] = {
            "name": doc.name,
            "employee": doc.employee,
            "employee_name": doc.employee_name,
            "status": doc.status,
            "docstatus": doc.docstatus,
            "custom_approval_status": doc.custom_approval_status,
            "leave_approver": doc.leave_approver,
            "leave_approver_name": doc.leave_approver_name,
            "category": category,
            "role_profile": role_profile,
            "required_designation": _get_required_designation_for_status(doc.custom_approval_status),
            "current_user_can_approve": (
                current_user == doc.leave_approver or 
                current_user == "Administrator" or
                _user_has_approver_designation(
                    current_user,
                    _get_required_designation_for_status(doc.custom_approval_status)
                )
            )
        }
    
    return result


@frappe.whitelist()
def fix_pending_leave_approvers():
    """
    One-time fix: Update leave_approver on all pending Leave Applications
    to use the dynamically resolved approver emails based on designation.
    
    This fixes existing leave applications that have stale/incorrect approver emails.
    Should be called once after deploying the designation-based lookup change.
    """
    clear_approver_cache()
    
    # Find all pending leave applications (docstatus=0, not approved/rejected)
    pending_apps = frappe.get_all(
        "Leave Application",
        filters={
            "docstatus": 0,
            "status": ["not in", ["Approved", "Rejected", "Cancelled"]]
        },
        fields=["name", "custom_approval_status", "leave_approver", "employee", "employee_name"]
    )
    
    fixed_count = 0
    for app in pending_apps:
        status = app.custom_approval_status
        if not status or status in ["Approved", "Rejected"]:
            continue
        
        # Determine which approver role is needed for the current status
        required_designations = _get_required_designation_for_status(status)
        if not required_designations:
            continue
        
        # Find the approver key from the designation(s)
        approver_key = None
        for key, desig in APPROVER_DESIGNATIONS.items():
            desig_list = desig if isinstance(desig, list) else [desig]
            if any(d in required_designations for d in desig_list):
                approver_key = key
                break
        
        if not approver_key:
            continue
        
        # Get the correct approver email
        correct_email = get_approver_email(approver_key)
        if correct_email and correct_email != app.leave_approver:
            approver_name = frappe.db.get_value("User", correct_email, "full_name")
            frappe.db.set_value("Leave Application", app.name, {
                "leave_approver": correct_email,
                "leave_approver_name": approver_name or approver_key
            }, update_modified=False)
            fixed_count += 1
    
    frappe.db.commit()
    return {"fixed": fixed_count, "total_pending": len(pending_apps)}


def _get_current_user_approver_role():
    """
    Check if the current user is an HR Coordinator, HOD (Area Sales Manager), or GM.
    Returns the approver role key ("HOD", "HR", "GM") or None.
    Used for permission checks.
    """
    user = frappe.session.user
    if not user or user in ["Administrator", "Guest"]:
        return None

    # Get current user's employee designation
    emp = frappe.db.get_value(
        "Employee",
        {"user_id": user},
        ["designation"],
        as_dict=True
    )
    if not emp:
        return None

    designation = emp.designation

    # Check all approver designations
    for role_key, desig in APPROVER_DESIGNATIONS.items():
        desig_list = desig if isinstance(desig, list) else [desig]
        if designation in desig_list:
            return role_key

    return None


def get_permission_query_conditions(user):
    """
    Custom permission query conditions for Leave Application.
    
    Allows the following users to see ALL Leave Applications:
    - Administrator / System Manager
    - HR Coordinator (Bindu T) - needs to approve all pending HR-stage applications
    - Area Sales Manager (HOD) - needs to see their team's applications
    - General Manager - needs to see all applications for final approval
    
    Standard users (employees) see only their own applications (Frappe default).
    
    This is registered in hooks.py as:
        permission_query_conditions = {"Leave Application": "...get_permission_query_conditions"}
    """
    if not user:
        user = frappe.session.user

    # Administrator sees everything - no extra conditions
    if user == "Administrator":
        return ""

    # Check if user has System Manager role
    if "System Manager" in frappe.get_roles(user):
        return ""

    # Check if user has HR Manager role (standard HRMS role)
    if "HR Manager" in frappe.get_roles(user):
        return ""

    # Check user's employee designation
    emp = frappe.db.get_value(
        "Employee",
        {"user_id": user},
        ["designation", "department"],
        as_dict=True
    )

    if emp:
        designation = emp.designation or ""

        # HR Coordinator: can see all leave applications (they approve all)
        hr_designations = APPROVER_DESIGNATIONS.get("HR", [])
        if isinstance(hr_designations, str):
            hr_designations = [hr_designations]
        if designation in hr_designations:
            return ""  # No restriction - see all

        # General Manager: can see all leave applications
        gm_designation = APPROVER_DESIGNATIONS.get("GM", "")
        if designation == gm_designation:
            return ""  # No restriction - see all

        # Area Sales Manager (HOD): can see applications from their department
        hod_designation = APPROVER_DESIGNATIONS.get("HOD", "")
        if designation == hod_designation:
            # Show all applications — HOD needs to approve Sales Executives
            return ""  # No restriction - see all

    # For all other employees: default Frappe behaviour
    # They see their own applications and ones where they are the leave_approver
    return (
        f"(`tabLeave Application`.`owner` = {frappe.db.escape(user)}"
        f" OR `tabLeave Application`.`leave_approver` = {frappe.db.escape(user)})"
    )


def has_permission(doc, ptype, user):
    """
    Custom document-level permission check for Leave Application.
    
    Grants read/write access to:
    - The document owner (the employee who applied)
    - The designated leave_approver
    - HR Coordinator, HOD (Area Sales Manager), GM — they need to see and act on documents
    - System Manager / Administrator
    
    Returns True to grant access, False to deny, None to use default Frappe logic.
    
    Registered in hooks.py as:
        has_permission = {"Leave Application": "...has_permission"}
    """
    if not user:
        user = frappe.session.user

    # Administrator always has access
    if user == "Administrator":
        return True

    # System Manager / HR Manager roles
    user_roles = frappe.get_roles(user)
    if "System Manager" in user_roles or "HR Manager" in user_roles:
        return True

    # Document owner (the employee who applied)
    if doc.owner == user:
        return True

    # Designated leave approver for this document
    if doc.leave_approver == user:
        return True

    # Check user's Employee designation
    emp = frappe.db.get_value(
        "Employee",
        {"user_id": user},
        ["designation"],
        as_dict=True
    )

    if emp:
        designation = emp.designation or ""

        # HR Coordinator: access to all leave applications
        hr_designations = APPROVER_DESIGNATIONS.get("HR", [])
        if isinstance(hr_designations, str):
            hr_designations = [hr_designations]
        if designation in hr_designations:
            return True

        # General Manager: access to all leave applications
        gm_designation = APPROVER_DESIGNATIONS.get("GM", "")
        if designation == gm_designation:
            return True

        # Area Sales Manager (HOD): access to all leave applications
        hod_designation = APPROVER_DESIGNATIONS.get("HOD", "")
        if designation == hod_designation:
            return True

    # Fallback: use Frappe default permission logic
    return None
