"""
Patch:

Case 1:
workflow_state = Draft
custom_approval_status = Rejected
→ custom_approval_status = Draft

Case 2:
status = Cancelled
custom_approval_status = Partially Approved
→ custom_approval_status = Cancelled

Run:
bench --site <sitename> execute chundakadan.patches.fix_rejected_draft_custom_status.execute
"""

import frappe


def execute():

    updated = 0

    # Case 1:
    # workflow_state = Draft
    # custom_approval_status = Rejected
    # -> Draft

    draft_records = frappe.db.get_all(
        "Leave Application",
        fields=[
            "name",
            "workflow_state",
            "custom_approval_status"
        ],
        filters={
            "workflow_state": "Draft",
            "custom_approval_status": "Rejected"
        },
        ignore_permissions=True,
    )

    for rec in draft_records:

        frappe.db.set_value(
            "Leave Application",
            rec.name,
            "custom_approval_status",
            "Draft",
            update_modified=False,
        )

        print(
            f"[{rec.name}] "
            "Rejected → Draft"
        )

        updated += 1


    # Case 2:
    # status = Cancelled
    # custom_approval_status = Partially Approved
    # -> Cancelled

    cancelled_records = frappe.db.get_all(
        "Leave Application",
        fields=[
            "name",
            "status",
            "custom_approval_status"
        ],
        filters={
            "status": "Cancelled",
            "custom_approval_status": "Partially Approved"
        },
        ignore_permissions=True,
    )

    for rec in cancelled_records:

        frappe.db.set_value(
            "Leave Application",
            rec.name,
            "custom_approval_status",
            "Cancelled",
            update_modified=False,
        )

        print(
            f"[{rec.name}] "
            "Partially Approved → Cancelled"
        )

        updated += 1


    frappe.db.commit()

    print(f"\n✅ Updated {updated} records")