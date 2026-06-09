"""Multi-step approval workflow for Expense Claim / Employee Advance /
Payment Request. Mirrors the Leave Application pattern but with an
amount-based chain:

  amount <= threshold  →  [Accounts Manager]                       (final)
  amount >  threshold  →  [Accounts Manager, GM Leave Approver]    (GM final)

The threshold lives on Chundakadan Settings.expense_approval_threshold
(default ₹5,000).

Wired from chundakadan/hooks.py as:
  doc_events[<DT>]["validate"]    = "chundakadan.chundakadan.api.expense_approval.validate"
  has_permission[<DT>]            = "chundakadan.chundakadan.api.expense_approval.has_permission"
  permission_query_conditions[<DT>] = "chundakadan.chundakadan.api.expense_approval.get_permission_query_conditions"

API:
  approve(doctype, docname)
  reject(doctype, docname, remarks=None)
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, now


# --- Per-doctype config -------------------------------------------------
# `amount_field` is the field on the parent doc we compare to the
# threshold. Each entry tells us how to find the money number.
DOCTYPE_CONFIG = {
    "Expense Claim": {
        "amount_field": "total_claimed_amount",
        "submit_on_final": True,
    },
    "Employee Advance": {
        "amount_field": "advance_amount",
        "submit_on_final": True,
    },
    "Payment Request": {
        "amount_field": "grand_total",
        "submit_on_final": True,
    },
}

# Role IDs used in the chain. Both roles already exist on the install
# with role-holders assigned (see Chundakadan memory).
ROLE_ACCOUNTS = "Accounts Manager"
ROLE_GM = "GM Leave Approver"

# Bypass roles — these users can approve regardless of who they're
# assigned to in the chain (also used for the perm gate).
ADMIN_ROLES = ("Administrator", "System Manager", "HR Manager")


# --- Helpers -----------------------------------------------------------

def _get_threshold() -> float:
    """Read the threshold from Chundakadan Settings; default ₹5,000."""
    try:
        return flt(frappe.db.get_single_value(
            "Chundakadan Settings", "expense_approval_threshold")) or 5000.0
    except Exception:
        return 5000.0


def _get_amount(doc) -> float:
    cfg = DOCTYPE_CONFIG.get(doc.doctype, {})
    return flt(doc.get(cfg.get("amount_field"))) or 0.0


def _get_approver_by_role(role: str) -> str | None:
    """Resolve a role to a specific User email.

    Preference order:
      1. User who is enabled AND linked to an active Employee
      2. First enabled User holding the role (any)
    Returns None if no role-holder exists.
    """
    users = frappe.get_all(
        "Has Role",
        filters={"role": role, "parenttype": "User"},
        fields=["parent"],
        ignore_permissions=True,
    )
    if not users:
        return None

    # Prefer users with an active Employee record
    for u in users:
        email = u["parent"]
        if not frappe.db.get_value("User", email, "enabled"):
            continue
        if frappe.db.exists("Employee", {"user_id": email, "status": "Active"}):
            return email

    # Fallback: first enabled user holding the role
    for u in users:
        email = u["parent"]
        if frappe.db.get_value("User", email, "enabled"):
            return email

    return None


def _build_chain(amount: float) -> list[str]:
    """Decide which roles need to approve, in order."""
    threshold = _get_threshold()
    if amount > threshold:
        return [ROLE_ACCOUNTS, ROLE_GM]
    return [ROLE_ACCOUNTS]


def _user_holds_role(user: str, role: str) -> bool:
    return bool(frappe.db.exists("Has Role", {"parent": user, "role": role}))


def _user_has_admin_role(user: str) -> bool:
    if user == "Administrator":
        return True
    for r in ADMIN_ROLES:
        if _user_holds_role(user, r):
            return True
    return False


def _caller_can_act_on(doc, user: str | None = None) -> bool:
    """Mirrors the leave workflow's gate. True if the user can move
    the doc forward at its current step."""
    user = user or frappe.session.user
    if _user_has_admin_role(user):
        return True

    if doc.get("current_approver") == user:
        return True

    idx = int(doc.get("current_approval_index") or 0)
    flow = doc.get("approval_flow") or []
    if 0 <= idx < len(flow):
        row = flow[idx]
        # Either the explicit approver email or any holder of the role
        row_approver = row.get("approver") if isinstance(row, dict) else row.approver
        row_role = row.get("approver_role") if isinstance(row, dict) else row.approver_role
        if row_approver == user:
            return True
        if row_role and _user_holds_role(user, row_role):
            return True
    return False


def _ensure_supported(doctype: str) -> None:
    if doctype not in DOCTYPE_CONFIG:
        frappe.throw(_("Approval workflow not configured for {0}").format(doctype))


# --- Hooks (called from hooks.py) -------------------------------------

def validate(doc, method=None):
    """`validate` hook. Generates the approval chain on first save
    OR when the amount changes such that the chain length should change.
    Skips already-submitted/cancelled docs.

    Also guards against direct Submit (docstatus 0→1 transition by
    someone who isn't using our approve() API): blocks the standard
    Submit button path when the chain isn't fully Approved yet.
    """
    if doc.doctype not in DOCTYPE_CONFIG:
        return

    # Auto-fill missing system requirements so users never hit
    # "X is required" errors mid-workflow. Idempotent — only fills blanks.
    _autofill_cost_center(doc)

    # Submit-time guard: if the doc is transitioning to docstatus=1 but
    # our chain hasn't been finalised, route the user to Approve button.
    if doc.get("docstatus") == 1 and doc.get("custom_approval_status") != "Approved":
        # Allow approve()'s set_user("Administrator") wrapped submit to pass
        if frappe.session.user != "Administrator":
            frappe.throw(_(
                "This {0} can only be submitted via the Approve workflow. "
                "Use the <b>Actions → Approve</b> button instead of Submit. "
                "Current approver: {1}"
            ).format(doc.doctype, doc.get("current_approver") or "—"))

    if int(doc.get("docstatus") or 0) > 0:
        return

    amount = _get_amount(doc)
    desired_roles = _build_chain(amount)

    existing_flow = doc.get("approval_flow") or []
    existing_roles = [
        (r.approver_role if hasattr(r, "approver_role") else r.get("approver_role"))
        for r in existing_flow
    ]

    # Only regenerate if the chain shape is wrong or flow is empty
    if existing_roles != desired_roles:
        _generate_approval_flow(doc, desired_roles)
        return

    # Even if roles match, make sure current_approver tracks current step
    idx = int(doc.get("current_approval_index") or 0)
    if 0 <= idx < len(existing_flow):
        row = existing_flow[idx]
        doc.current_approver = (
            row.approver if hasattr(row, "approver") else row.get("approver")
        )
        _sync_standard_approver_field(doc)


def _generate_approval_flow(doc, roles: list[str]):
    """Reset the approval chain on the doc. Throws if any role has no
    role-holder configured."""
    doc.set("approval_flow", [])
    for role in roles:
        approver = _get_approver_by_role(role)
        if not approver:
            frappe.throw(_(
                "Cannot create approval chain — no active user holds the "
                "role '{0}'. Ask an admin to assign this role to a user "
                "via the User list."
            ).format(role))
        doc.append("approval_flow", {
            "approver": approver,
            "approver_role": role,
            "status": "Pending",
        })
    doc.current_approval_index = 0
    doc.current_approver = doc.approval_flow[0].approver
    doc.custom_approval_status = "Pending"
    _sync_standard_approver_field(doc)


def _sync_standard_approver_field(doc):
    """Mirror our current_approver into ERPNext's standard approver
    field (if the doctype has one) so standard mandatory validation
    passes without the user touching it manually.

      Expense Claim   → expense_approver
      Employee Advance → no standard approver field; no-op
      Payment Request → no standard approver field; no-op
    """
    if doc.doctype == "Expense Claim" and doc.meta.has_field("expense_approver"):
        if doc.get("current_approver"):
            doc.expense_approver = doc.current_approver


def _autofill_cost_center(doc):
    """Auto-fill Cost Center on expense rows where it's missing.

    Resolution chain:
      1. Employee.payroll_cost_center (HR field on Employee)
      2. Department.cost_center (Cost Center linked to Department)
      3. Company.cost_center (default on Company)
      4. First non-group Cost Center belonging to the company
    """
    if doc.doctype != "Expense Claim":
        return
    rows_needing_cc = [r for r in (doc.get("expenses") or [])
                       if not r.get("cost_center")]
    if not rows_needing_cc:
        return

    cc = None

    # 1. Employee's payroll_cost_center
    employee = doc.get("employee")
    if employee:
        cc = frappe.db.get_value("Employee", employee, "payroll_cost_center")

    # 2. Department.cost_center
    if not cc:
        dept = doc.get("department") or frappe.db.get_value(
            "Employee", employee, "department") if employee else None
        if dept:
            cc = frappe.db.get_value("Department", dept, "cost_center")

    # 3. Company.cost_center
    company = doc.get("company")
    if not cc and company:
        cc = frappe.db.get_value("Company", company, "cost_center")

    # 4. Any non-group Cost Center for the company
    if not cc and company:
        cc = frappe.db.get_value(
            "Cost Center",
            {"company": company, "is_group": 0, "disabled": 0},
            "name",
        )

    if not cc:
        return  # nothing to fill with, let ERPNext surface its error

    for r in rows_needing_cc:
        r.cost_center = cc


# --- API: approve / reject --------------------------------------------

@frappe.whitelist()
def approve(doctype: str, docname: str):
    """Mark the current step as approved; advance to next step or
    submit if final. Returns {success: True, status: <new status>}."""
    _ensure_supported(doctype)
    doc = frappe.get_doc(doctype, docname)

    if doc.get("custom_approval_status") in ("Approved", "Rejected"):
        frappe.throw(_("This {0} has already been finalised.").format(doctype))

    if not _caller_can_act_on(doc):
        frappe.throw(_("You don't have permission to approve this {0}.")
                     .format(doctype))

    idx = int(doc.get("current_approval_index") or 0)
    flow = doc.get("approval_flow") or []
    if not flow or idx >= len(flow):
        frappe.throw(_("Approval chain is not configured."))

    current_user = frappe.session.user
    row = flow[idx]
    row.status = "Approved"
    row.approved_on = now()
    # Record who actually clicked (may differ from the originally-assigned
    # approver if another role-holder acted)
    if row.approver != current_user and not _user_has_admin_role(current_user):
        row.approver = current_user

    is_final = (idx + 1) >= len(flow)
    cfg = DOCTYPE_CONFIG[doctype]

    # CRITICAL — switch user to bypass ERPNext's standard perm checks on
    # submit (Expense Claim / EA / PR all have Employee read-perm checks
    # that block non-HR users at submit time).
    original_user = frappe.session.user
    try:
        frappe.set_user("Administrator")

        if is_final:
            doc.custom_approval_status = "Approved"
            doc.current_approver = None
            # Expense Claim's standard `approval_status` field must be
            # 'Approved' or 'Rejected' before submit() will succeed
            if doc.meta.has_field("approval_status"):
                doc.approval_status = "Approved"
            if int(doc.docstatus or 0) == 0 and cfg.get("submit_on_final"):
                doc.submit()
            else:
                doc.save(ignore_permissions=True)
        else:
            next_idx = idx + 1
            doc.current_approval_index = next_idx
            doc.current_approver = flow[next_idx].approver
            doc.custom_approval_status = "Partially Approved"
            _sync_standard_approver_field(doc)
            doc.save(ignore_permissions=True)
    finally:
        frappe.set_user(original_user)

    return {"success": True, "status": doc.custom_approval_status,
            "current_approver": doc.current_approver}


@frappe.whitelist()
def reject(doctype: str, docname: str, remarks: str | None = None):
    """Mark the doc as Rejected. Stays Draft so user can edit + resubmit."""
    _ensure_supported(doctype)
    doc = frappe.get_doc(doctype, docname)

    if doc.get("custom_approval_status") in ("Approved", "Rejected"):
        frappe.throw(_("This {0} has already been finalised.").format(doctype))

    if not _caller_can_act_on(doc):
        frappe.throw(_("You don't have permission to reject this {0}.")
                     .format(doctype))

    idx = int(doc.get("current_approval_index") or 0)
    flow = doc.get("approval_flow") or []
    if not flow or idx >= len(flow):
        frappe.throw(_("Approval chain is not configured."))

    current_user = frappe.session.user
    row = flow[idx]
    row.status = "Rejected"
    row.approved_on = now()
    row.remarks = remarks or ""
    if row.approver != current_user and not _user_has_admin_role(current_user):
        row.approver = current_user

    doc.custom_approval_status = "Rejected"
    doc.current_approver = None
    # Mirror to standard ERPNext approval_status if it exists
    if doc.meta.has_field("approval_status"):
        doc.approval_status = "Rejected"

    original_user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        doc.save(ignore_permissions=True)
    finally:
        frappe.set_user(original_user)

    return {"success": True, "status": "Rejected"}


# --- Permission gate --------------------------------------------------

def has_permission(doc, ptype="read", user=None):
    """Doc-level perm gate. Users see/edit a doc if they are:
      - Admin / System Manager / HR Manager
      - The applicant (owner)
      - The current_approver
      - A holder of any role in the approval_flow chain (any step)
    """
    if doc.doctype not in DOCTYPE_CONFIG:
        return None  # let standard perms decide

    user = user or frappe.session.user
    if _user_has_admin_role(user):
        return True
    if doc.get("owner") == user:
        return True

    # Employee Advance & Expense Claim have an `employee` field; allow
    # the linked employee's user to read their own doc
    employee = doc.get("employee")
    if employee:
        emp_user = frappe.db.get_value("Employee", employee, "user_id")
        if emp_user == user:
            return True

    if doc.get("current_approver") == user:
        return True

    flow = doc.get("approval_flow") or []
    for row in flow:
        approver = row.approver if hasattr(row, "approver") else row.get("approver")
        role = row.approver_role if hasattr(row, "approver_role") else row.get("approver_role")
        if approver == user:
            return True
        if role and _user_holds_role(user, role):
            return True

    return False


def get_permission_query_conditions(user=None):
    """List-view filter. Returns SQL fragment limiting rows to those
    the user can see."""
    user = user or frappe.session.user
    if _user_has_admin_role(user):
        return ""

    user_roles = frappe.get_roles(user)
    role_clause = ""
    if user_roles:
        role_list = ", ".join(frappe.db.escape(r) for r in user_roles)
        # Doctype name is injected by caller; we use %(doctype)s placeholder
        # via Frappe's standard mechanism. But since this hook is per-DT,
        # we just use the parent column to point at the approval_flow rows.
        role_clause = (
            f" OR EXISTS (SELECT 1 FROM `tabChundakadan Approval Detail` af "
            f"WHERE af.parent = `tab%s`.name AND af.approver_role IN ({role_list}))"
        )

    # owner / current_approver / employee.user_id direct
    user_q = frappe.db.escape(user)
    base = (
        f"(`tab%s`.owner = {user_q} OR "
        f"`tab%s`.current_approver = {user_q}"
    )

    # We don't know the DocType in this hook signature — Frappe passes it
    # implicitly via the caller. The placeholder %s gets replaced by
    # Frappe's standard list-view machinery when the SQL is generated.
    # Actually Frappe expects the doctype name literally in the string.
    # So we need to be doctype-aware. The framework calls this hook
    # separately per DT — we can't tell which one. Workaround: detect
    # via the caller stack. Simpler: return separate functions, one per
    # doctype (wired in hooks.py).
    raise NotImplementedError(
        "Use the doctype-specific wrappers below instead.")


def _query_conditions_for(doctype: str, user: str) -> str:
    if _user_has_admin_role(user):
        return ""
    user_q = frappe.db.escape(user)
    table = f"`tab{doctype}`"
    parts = [
        f"{table}.owner = {user_q}",
        f"{table}.current_approver = {user_q}",
    ]

    # employee.user_id link if the doctype has an `employee` field
    if frappe.get_meta(doctype).has_field("employee"):
        parts.append(
            f"{table}.employee IN (SELECT name FROM `tabEmployee` "
            f"WHERE user_id = {user_q})"
        )

    user_roles = frappe.get_roles(user)
    if user_roles:
        role_list = ", ".join(frappe.db.escape(r) for r in user_roles)
        parts.append(
            f"EXISTS (SELECT 1 FROM `tabChundakadan Approval Detail` af "
            f"WHERE af.parent = {table}.name AND af.parenttype = {frappe.db.escape(doctype)} "
            f"AND af.approver_role IN ({role_list}))"
        )

    return "(" + " OR ".join(parts) + ")"


def get_permission_query_conditions_expense_claim(user=None):
    return _query_conditions_for("Expense Claim", user or frappe.session.user)


def get_permission_query_conditions_employee_advance(user=None):
    return _query_conditions_for("Employee Advance", user or frappe.session.user)


def get_permission_query_conditions_payment_request(user=None):
    return _query_conditions_for("Payment Request", user or frappe.session.user)
