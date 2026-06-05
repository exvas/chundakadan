# Copyright (c) 2026, Chundakadan
# Install / migrate hooks. Lives at chundakadan.install.* — wired
# from chundakadan/hooks.py as `before_install` + `before_migrate`.

import subprocess
import sys


# Pinned to match chundakadan/pyproject.toml so a manual install AND
# the auto-installer pull the exact same version.
_FIREBASE_ADMIN_PIN = "firebase-admin>=6.5.0,<8.0.0"


def ensure_firebase_admin_installed(*args, **kwargs):
    """Idempotent: `pip install firebase-admin` if it isn't already
    importable in this Python env. Skips silently when already
    installed; logs without failing if install fails (so a migrate
    doesn't break in restricted/Frappe-Cloud-like environments where
    pip might be read-only — deps come from pyproject.toml there
    anyway).

    Wired as both `before_install` (first-time `bench install-app
    chundakadan`) and `before_migrate` (every `bench migrate`). Means:
      - Fresh clone + bench migrate → firebase-admin appears
      - Upgrade existing bench → if dep was somehow stripped, restored
      - Frappe Cloud deploy → pyproject.toml handles it via build
        step; this hook is a safety net.
    """
    try:
        import firebase_admin  # noqa: F401
        return
    except ImportError:
        pass

    print(f"chundakadan.install: installing {_FIREBASE_ADMIN_PIN}…")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", _FIREBASE_ADMIN_PIN],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        print("chundakadan.install: firebase-admin installed ✓")
    except Exception as e:
        # Non-fatal — push notifications will just no-op (with a log
        # entry in chundakadan.push.import) until firebase-admin is
        # available. The rest of the migrate proceeds normally.
        print(
            f"chundakadan.install: could not auto-install firebase-admin: {e}\n"
            "  Push notifications will be disabled. To enable, run:\n"
            "    bench pip install firebase-admin"
        )


def ensure_fcm_credentials_field(*args, **kwargs):
    """Idempotent: create Chundakadan Settings.fcm_credentials_json
    Custom Field if it doesn't exist. HR pastes the Firebase service-
    account JSON contents into this field via the desk — no SSH /
    filesystem needed. push.py checks this field first when initialising
    firebase-admin.

    Wired as before_migrate so the field is always present after a
    chundakadan deploy on any host (self-hosted bench, Frappe Cloud,
    fresh Ubuntu).
    """
    import frappe

    if not frappe.db.exists("DocType", "Chundakadan Settings"):
        # Singleton not yet created — first install hasn't finished.
        # Skip; will get re-attempted on the next migrate.
        return

    if frappe.db.exists("Custom Field", "Chundakadan Settings-fcm_credentials_json"):
        return

    try:
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Chundakadan Settings",
            "fieldname": "fcm_credentials_json",
            "label": "FCM Credentials JSON",
            "fieldtype": "Long Text",
            "insert_after": "modified",  # adjust if you want a specific section
            "description": (
                "Paste the contents of the Firebase service-account JSON "
                "(downloaded from Firebase Console → Project Settings → "
                "Service accounts → Generate new private key). The mobile "
                "push helper reads from here first, then falls back to "
                "/home/frappe/firebase-service-account.json."
            ),
            "module": "Chundakadan",
            "translatable": 0,
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        print("chundakadan.install: Custom Field 'fcm_credentials_json' "
              "created on Chundakadan Settings")
    except Exception as e:
        print(f"chundakadan.install: could not create FCM field: {e}")


def ensure_employee_payroll_fields(*args, **kwargs):
    """Idempotent: add 5 Custom Fields to Employee for payroll disbursement.

    Standard ERPNext Employee usually ships PAN/bank/IFSC fields, but
    this install had them stripped (likely an early customization).
    Rather than re-enabling standard fields (risky if any code still
    references the old definitions), we add custom_* fields:

      custom_salary_mode        Select   Cash / Bank Transfer / Cheque
      custom_bank_name          Data
      custom_bank_account_no    Data
      custom_ifsc_code          Data
      custom_uan_number         Data     (PF compliance, optional)

    All placed in a new 'Payroll Disbursement' section so HR sees them
    grouped on the Employee form.
    """
    import frappe

    if not frappe.db.exists("DocType", "Employee"):
        return

    fields = [
        {
            "fieldname": "custom_payroll_section",
            "label": "Payroll Disbursement",
            "fieldtype": "Section Break",
            "insert_after": "company_email",
            "collapsible": 1,
        },
        {
            "fieldname": "custom_salary_mode",
            "label": "Salary Mode",
            "fieldtype": "Select",
            "options": "Cash\nBank Transfer\nCheque",
            "default": "Cash",
            "insert_after": "custom_payroll_section",
            "in_standard_filter": 1,
            "description": "How this employee's salary is paid each month.",
        },
        {
            "fieldname": "custom_bank_name",
            "label": "Bank Name",
            "fieldtype": "Data",
            "insert_after": "custom_salary_mode",
            "depends_on": "eval:doc.custom_salary_mode == 'Bank Transfer'",
        },
        {
            "fieldname": "custom_bank_account_no",
            "label": "Bank A/C No",
            "fieldtype": "Data",
            "insert_after": "custom_bank_name",
            "depends_on": "eval:doc.custom_salary_mode == 'Bank Transfer'",
        },
        {
            "fieldname": "custom_ifsc_code",
            "label": "IFSC Code",
            "fieldtype": "Data",
            "insert_after": "custom_bank_account_no",
            "depends_on": "eval:doc.custom_salary_mode == 'Bank Transfer'",
        },
        {
            "fieldname": "custom_uan_number",
            "label": "UAN (PF)",
            "fieldtype": "Data",
            "insert_after": "custom_ifsc_code",
            "description": "Universal Account Number for PF — optional, "
                           "only needed if you start filing PF returns.",
        },
    ]

    created = 0
    for spec in fields:
        cf_name = f"Employee-{spec['fieldname']}"
        if frappe.db.exists("Custom Field", cf_name):
            continue
        try:
            doc = frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "Employee",
                "module": "Chundakadan",
                "translatable": 0,
                **spec,
            })
            doc.insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            print(f"chundakadan.install: could not create {cf_name}: {e}")

    if created:
        frappe.db.commit()
        print(f"chundakadan.install: created {created} Employee payroll fields")


def ensure_visit_log_visit_type_field(*args, **kwargs):
    """Idempotent: create Customer Visit Log.visit_type Custom Field
    so HR can filter "real customer visits" vs "mobile check-in /
    check-out" auto-pairs.

    Backfills existing rows on first creation:
      - customer_name == "Check-In"  -> visit_type = "Check-In"
      - customer_name == "Check-Out" -> visit_type = "Check-Out"
      - everything else              -> visit_type = "Customer Visit"
    """
    import frappe

    if not frappe.db.exists("DocType", "Customer Visit Log"):
        return

    field_already_exists = frappe.db.exists(
        "Custom Field", "Customer Visit Log-visit_type"
    )

    if not field_already_exists:
        try:
            frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "Customer Visit Log",
                "fieldname": "visit_type",
                "label": "Visit Type",
                "fieldtype": "Select",
                "options": "Customer Visit\nCheck-In\nCheck-Out",
                "default": "Customer Visit",
                "insert_after": "customer_name",
                "in_standard_filter": 1,  # appears in list view filter sidebar
                "in_list_view": 1,
                "description": (
                    "Distinguishes deliberate customer visits from "
                    "mobile-app Check-In / Check-Out auto-pair rows. "
                    "Check-In/Check-Out rows are created automatically "
                    "from create_employee_checkin and shouldn't be "
                    "treated as customer visits in reports."
                ),
                "module": "Chundakadan",
                "translatable": 0,
            }).insert(ignore_permissions=True)
            frappe.db.commit()
            print(
                "chundakadan.install: Custom Field 'visit_type' created "
                "on Customer Visit Log"
            )
        except Exception as e:
            print(
                f"chundakadan.install: could not create visit_type field: {e}"
            )
            return

    # Backfill: Frappe's Custom Field `default` sets every existing row
    # to "Customer Visit" the moment the field is created, so guarding
    # on `WHERE visit_type IS NULL` matches zero rows. Use customer_name
    # as the source of truth — those literal "Check-In" / "Check-Out"
    # strings only come from create_employee_checkin's mirror code path.
    # Idempotent: subsequent runs touch nothing because the visit_type
    # is already correct.
    try:
        frappe.db.sql("""
            UPDATE `tabCustomer Visit Log`
               SET visit_type = customer_name
             WHERE customer_name IN ('Check-In', 'Check-Out')
               AND (visit_type IS NULL OR visit_type != customer_name)
        """)
        frappe.db.commit()
        rows = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
        if rows:
            print(
                f"chundakadan.install: re-tagged visit_type on {rows} "
                "auto-paired Customer Visit Log rows"
            )
    except Exception as e:
        print(
            f"chundakadan.install: could not backfill visit_type: {e}"
        )


def ensure_visit_log_location_field(*args, **kwargs):
    """Idempotent: create Customer Visit Log.custom_location Custom Field
    if missing. The reverse-geocoder in chundakadan/utils/geocode.py
    writes the resolved street address into `custom_location` — but
    Customer Visit Log doesn't ship with that field, so visit-log
    addresses were silently dropped. Employee Checkin already has its
    own custom_location field.
    """
    import frappe

    if not frappe.db.exists("DocType", "Customer Visit Log"):
        return

    if frappe.db.exists("Custom Field", "Customer Visit Log-custom_location"):
        return

    try:
        # Insert AFTER the standard latitude/longitude pair so it groups
        # naturally with the GPS fields in the form.
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Customer Visit Log",
            "fieldname": "custom_location",
            "label": "Location",
            "fieldtype": "Small Text",
            "insert_after": "longitude",
            "read_only": 1,
            "description": (
                "Reverse-geocoded street address from OpenStreetMap. "
                "Auto-populated by chundakadan/utils/geocode.py via the "
                "after_insert hook on Customer Visit Log."
            ),
            "module": "Chundakadan",
            "translatable": 0,
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        print(
            "chundakadan.install: Custom Field 'custom_location' created "
            "on Customer Visit Log"
        )
    except Exception as e:
        print(
            f"chundakadan.install: could not create visit log location field: {e}"
        )
