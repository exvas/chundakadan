"""
Patch: Sync Leave Application.status with custom_approval_status

Mapping:
------------------------------------
custom_approval_status      → status
------------------------------------
Pending                     → Pending
Partially Approved          → Partially Approved
Rejected                    → Rejected

Approved is skipped because existing records are already correct.

Run:
bench --site <sitename> execute chundakadan.patches.fix_leave_application_status.execute
"""

import frappe


def _resolve_status(custom_status, current_status):
    custom_status = (custom_status or "").strip()

    # Skip approved records
    if custom_status == "Approved":
        return current_status

    mapping = {
        "Pending": "Pending",
        "Partially Approved": "Partially Approved",
        "Rejected": "Rejected",
    }

    return mapping.get(custom_status, current_status)


def execute():
    records = frappe.db.get_all(
        "Leave Application",
        fields=["name", "status", "custom_approval_status"],
        ignore_permissions=True,
    )

    updated = 0
    skipped = 0

    for rec in records:
        old_status = rec.status
        new_status = _resolve_status(
            rec.custom_approval_status,
            old_status,
        )

        if old_status != new_status:
            frappe.db.set_value(
                "Leave Application",
                rec.name,
                "status",
                new_status,
                update_modified=False,
            )

            print(
                f"[{rec.name}] "
                f"'{old_status}' → '{new_status}'"
            )

            updated += 1
        else:
            skipped += 1

    frappe.db.commit()

    print(
        f"\n✅ Done | Updated: {updated} | Skipped: {skipped}"
    )