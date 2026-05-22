"""
Patch:
Force submit historical Leave Applications
(by bypassing validations)

Run:
bench --site <sitename> execute chundakadan.patches.force_submit_selected_leave_applications.execute
"""

import frappe


def execute():

    leave_applications = [
        "HR-LAP-2026-00136",
        "HR-LAP-2026-00135",
        "HR-LAP-2026-00141",
        "HR-LAP-2026-00156",
        "HR-LAP-2026-00111",
        "HR-LAP-2026-00062",
    ]

    submitted = 0
    amended = 0
    skipped = 0

    for docname in leave_applications:

        try:

            doc = frappe.get_doc(
                "Leave Application",
                docname
            )

            # Draft docs
            if doc.docstatus == 0:

                # Fix invalid status values
                if doc.status == "Partially Approved":
                    frappe.db.set_value(
                        "Leave Application",
                        doc.name,
                        "status",
                        "Approved",
                        update_modified=False
                    )

                # Force submit
                frappe.db.set_value(
                    "Leave Application",
                    doc.name,
                    "docstatus",
                    1,
                    update_modified=False
                )

                print(
                    f"[{docname}] Force submitted"
                )

                submitted += 1


            # Cancelled docs
            elif doc.docstatus == 2:

                amended_doc = frappe.copy_doc(doc)

                amended_doc.amended_from = doc.name

                amended_doc.insert(
                    ignore_permissions=True
                )

                frappe.db.set_value(
                    "Leave Application",
                    amended_doc.name,
                    "docstatus",
                    1,
                    update_modified=False
                )

                print(
                    f"[{docname}] "
                    f"Amended -> {amended_doc.name}"
                )

                amended += 1


            else:

                print(
                    f"[{docname}] "
                    "Already submitted"
                )

                skipped += 1

        except Exception as e:

            print(
                f"[{docname}] Error: {str(e)}"
            )

    frappe.db.commit()

    print(
        f"\n✅ Submitted: {submitted}"
        f"\n🔁 Amended: {amended}"
        f"\n⏭ Skipped: {skipped}"
    )