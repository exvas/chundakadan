"""
Patch: Migrate historical Leave Application custom_approval_status values
to the new 4-value system used by chundakadan.chundakadan.api.leave.

OLD statuses (multi-stage)               → NEW status
--------------------------------------------------------
Pending HOD                              → Pending           (nothing approved yet)
Approved HOD  (not fully approved)       → Partially Approved (HOD done, HR/GM pending)
Pending HR                               → Partially Approved (HOD already approved)
Approved HR   (not fully approved)       → Partially Approved (HR done, GM still pending)
Pending GM                               → Partially Approved (HOD+HR already approved)
Approved GM   (submitted / Approved)     → Approved
Approved HR   (submitted / Approved)     → Approved          (final step for GM-category)
Rejected / "Rejected "                   → Rejected
"Pending " (with whitespace)             → Pending

Run via bench console:
    bench --site <sitename> execute chundakadan.patches.fix_leave_application_statuses.execute
"""

import frappe


def _resolve_new_status(old_status, is_fully_approved):
    """Return the correct new status for a given old custom_approval_status."""
    old = (old_status or "").strip()

    # Already in the new 4-value format — leave untouched
    if old in ("Pending", "Partially Approved", "Approved", "Rejected"):
        return old

    # Fully submitted / HRMS-approved document → always "Approved"
    if is_fully_approved and (old.startswith("Approved") or old.startswith("Pending")):
        return "Approved"

    # Rejected variants (handle trailing/leading whitespace)
    if old.lower().startswith("rejected"):
        return "Rejected"

    # "Pending HOD" → nothing approved yet
    if old in ("Pending HOD",):
        return "Pending"

    # Intermediate states — at least one approver has already acted
    if old in (
        "Approved HOD",   # HOD approved, HR next
        "Pending HR",     # HOD approved, HR waiting
        "Approved HR",    # HR approved, GM next  (non-submitted)
        "Pending GM",     # HR approved, GM waiting
    ):
        return "Partially Approved"

    # Generic "Pending X" not in the known list
    # (means a previous approver is done, this stage is now pending)
    if old.startswith("Pending "):
        return "Partially Approved"

    # Generic "Approved X" on a non-submitted doc
    if old.startswith("Approved "):
        return "Partially Approved"

    # Fallback: return stripped value (no mapping found)
    return old


def execute():
    records = frappe.db.get_all(
        "Leave Application",
        fields=["name", "custom_approval_status", "status", "docstatus"],
        ignore_permissions=True,
    )

    updated = 0
    skipped = 0

    for rec in records:
        old_status = rec.custom_approval_status or ""
        is_fully_approved = rec.docstatus == 1 or rec.status == "Approved"
        new_status = _resolve_new_status(old_status, is_fully_approved)

        if new_status != old_status:
            frappe.db.set_value(
                "Leave Application",
                rec.name,
                "custom_approval_status",
                new_status,
                update_modified=False,
            )
            print(f"  [{rec.name}]  '{old_status}'  →  '{new_status}'")
            updated += 1
        else:
            skipped += 1

    frappe.db.commit()
    print(f"\n✅  Done.  Updated: {updated}  |  Skipped (no change): {skipped}")
