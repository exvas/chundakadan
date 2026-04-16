import frappe

def execute():
    # Delete the report "Monthly Attendance Sheet CK" if it exists
    if frappe.db.exists("Report", "Monthly Attendance Sheet CK"):
        frappe.delete_doc("Report", "Monthly Attendance Sheet CK", ignore_missing=True, force=True)
        frappe.db.commit()
