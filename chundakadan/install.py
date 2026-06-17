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


_HOLIDAYS_PIN = "holidays>=0.50"


def ensure_holidays_library_installed(*args, **kwargs):
    """Idempotent: `pip install holidays` if it isn't already importable.

    The `holidays` Python library provides India + Kerala (KL) holiday
    dates auto-calculated for any year. seed/holiday_list.py uses it
    to generate Holiday List entries that include Onam, Vishu, Eid,
    Diwali, etc. without needing manual yearly updates.

    Non-fatal — if install fails, holiday_list.py falls back to its
    hardcoded _HOLIDAYS_BY_YEAR map (good through 2030).
    """
    try:
        import holidays  # noqa: F401
        return
    except ImportError:
        pass

    print(f"chundakadan.install: installing {_HOLIDAYS_PIN}…")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", _HOLIDAYS_PIN],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        print("chundakadan.install: holidays installed ✓")
    except Exception as e:
        print(
            f"chundakadan.install: could not auto-install holidays: {e}\n"
            "  Falls back to hardcoded 2026-2030 holiday map."
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


def ensure_payroll_config_fields(*args, **kwargs):
    """Idempotent: add 3 Custom Fields to Chundakadan Settings that
    drive payroll behaviour dynamically:

      esi_wage_ceiling   Int    Default 21000  — ESI cuts off above this
      pf_wage_ceiling    Int    Default 15000  — PF capped at this
      payroll_basis      Select Calendar / Working / Fixed 30 days

    seed_salary_components() reads these at run time + bakes the
    current values into Salary Component formulas. To change a
    ceiling: HR edits Chundakadan Settings then re-runs
    seed_salary_components() — no code redeploy needed.
    """
    import frappe

    if not frappe.db.exists("DocType", "Chundakadan Settings"):
        return

    fields = [
        {
            "fieldname": "payroll_config_section",
            "label": "Payroll Configuration",
            "fieldtype": "Section Break",
            "insert_after": "fcm_credentials_json",
            "collapsible": 1,
        },
        {
            "fieldname": "esi_wage_ceiling",
            "label": "ESI Wage Ceiling (₹)",
            "fieldtype": "Int",
            "default": "21000",
            "insert_after": "payroll_config_section",
            "description": (
                "Monthly gross-wages threshold below which ESI applies. "
                "Indian statutory ceiling = ₹21,000 (₹25,000 for persons "
                "with disability). Update + re-run "
                "chundakadan.seed.payroll_rebuild.seed_salary_components "
                "to propagate."
            ),
        },
        {
            "fieldname": "esi_extended_ceiling",
            "label": "ESI Extended Cutoff (₹)",
            "fieldtype": "Int",
            "default": "42000",
            "insert_after": "esi_wage_ceiling",
            "description": (
                "Chundakadan-specific: ESI continues for employees up "
                "to this gross. Between ESI Wage Ceiling and this cutoff, "
                "contribution is calculated on the capped wage. Above "
                "this cutoff, no ESI."
            ),
        },
        {
            "fieldname": "pf_wage_ceiling",
            "label": "PF Wage Ceiling (₹)",
            "fieldtype": "Int",
            "default": "15000",
            "insert_after": "esi_extended_ceiling",
            "description": (
                "Cap on Basic+DA for PF computation. Indian statutory "
                "ceiling = ₹15,000. PF = 12% of min(basic, ceiling)."
            ),
        },
        {
            "fieldname": "payroll_basis",
            "label": "Payroll Basis",
            "fieldtype": "Select",
            "options": "Fixed 30 Days\nCalendar Days\nWorking Days",
            "default": "Fixed 30 Days",
            "insert_after": "pf_wage_ceiling",
            "description": (
                "How days are counted on Salary Slips. "
                "Fixed 30 — always divides by 30 regardless of month length. "
                "Calendar — actual days in month (28-31). "
                "Working — excludes holidays + weekly off."
            ),
        },
    ]

    created = 0
    for spec in fields:
        cf_name = f"Chundakadan Settings-{spec['fieldname']}"
        if frappe.db.exists("Custom Field", cf_name):
            continue
        try:
            frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "Chundakadan Settings",
                "module": "Chundakadan",
                "translatable": 0,
                **spec,
            }).insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            print(f"chundakadan.install: could not create {cf_name}: {e}")

    # Custom Field `default` only applies to new docs — Chundakadan
    # Settings is an existing Singleton, so its values stay NULL / 0
    # unless we explicitly set them. Backfill any field whose Singleton
    # value is empty.
    if frappe.db.exists("DocType", "Chundakadan Settings"):
        defaults = {
            "esi_wage_ceiling": 21000,
            "esi_extended_ceiling": 42000,
            "pf_wage_ceiling": 15000,
            "payroll_basis": "Fixed 30 Days",
        }
        try:
            settings = frappe.get_single("Chundakadan Settings")
            changed = False
            for fn, default_val in defaults.items():
                current = settings.get(fn)
                if not current:
                    settings.set(fn, default_val)
                    changed = True
            if changed:
                settings.flags.ignore_permissions = True
                settings.save()
                print("chundakadan.install: backfilled payroll defaults "
                      "on Chundakadan Settings singleton")
        except Exception as e:
            print(f"chundakadan.install: could not backfill defaults: {e}")

    if created:
        frappe.db.commit()
        print(f"chundakadan.install: created {created} payroll config fields")


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


def ensure_visit_log_sales_user_create_perm(*args, **kwargs):
    """Grant Sales User create + delete on Customer Visit Log.

    Hit 2026-06-06: Razeel (sales@chundakadan.in) holds Sales User
    role via CDN Sales Admin profile and tried to log a Field Visit
    Logger entry from the mobile app — got 403 'No permission for
    Customer Visit Log'. Audit showed the doctype's Custom DocPerm
    rows give Sales User read+write but NOT create:

      Sales Person:  read write create delete
      System Manager: read write create delete
      Sales User:    read write   ✗     ✗     ← create blocked
      HR User:       read write create delete

    The mobile endpoint already uses ignore_permissions=True (field_sales
    commit cbb2415) so that path works, but the desk UI still rejects
    Sales User creates. Grant create + delete here so both paths work.

    Idempotent: skips if Sales User already has create=1.
    """
    import frappe

    if not frappe.db.exists("DocType", "Customer Visit Log"):
        return

    existing = frappe.db.get_value(
        "Custom DocPerm",
        {"parent": "Customer Visit Log", "role": "Sales User"},
        ["name", "create", "delete"],
        as_dict=True,
    )

    if existing and existing.get("create") and existing.get("delete"):
        return

    try:
        if existing:
            # Upgrade the existing Sales User row in place
            doc = frappe.get_doc("Custom DocPerm", existing["name"])
            doc.create = 1
            doc.delete = 1
            doc.flags.ignore_permissions = True
            doc.save()
            print("chundakadan.install: upgraded Sales User Custom DocPerm "
                  "on Customer Visit Log (added create + delete)")
        else:
            # Should not happen given the audit showed a row exists,
            # but handle defensively.
            frappe.get_doc({
                "doctype": "Custom DocPerm",
                "parent": "Customer Visit Log",
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": "Sales User",
                "read": 1, "write": 1, "create": 1, "delete": 1,
            }).insert(ignore_permissions=True)
            print("chundakadan.install: created Sales User Custom DocPerm "
                  "on Customer Visit Log")
        frappe.db.commit()
        frappe.clear_cache(doctype="Customer Visit Log")
    except Exception as e:
        print(f"chundakadan.install: could not adjust visit-log perm: {e}")


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


# ----------------------------------------------------------------------
# Expense / Advance / Payment Request approval workflow
# ----------------------------------------------------------------------
# Adds the same 4 custom fields to all 3 doctypes plus a threshold
# field on Chundakadan Settings. Mirrors the Leave Application multi-
# step approval shape but with an amount-based chain length.

_APPROVAL_DOCTYPES = [
    ("Expense Claim",     "total_claimed_amount", "total_sanctioned_amount"),
    ("Employee Advance",  "advance_amount",       "purpose"),
    ("Payment Request",   "grand_total",          "subject"),
]


def ensure_expense_approval_fields(*args, **kwargs):
    """Idempotent: add custom fields to Expense Claim / Employee Advance /
    Payment Request for the multi-step approval workflow, plus an
    `expense_approval_threshold` field on Chundakadan Settings."""
    import frappe

    common_fields = [
        {
            "fieldname": "approval_section",
            "label": "Approval Workflow",
            "fieldtype": "Section Break",
            "collapsible": 1,
        },
        {
            "fieldname": "custom_approval_status",
            "label": "Approval Status",
            "fieldtype": "Select",
            "options": "\nPending\nPartially Approved\nApproved\nRejected",
            "read_only": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
        },
        {
            "fieldname": "current_approver",
            "label": "Current Approver",
            "fieldtype": "Link",
            "options": "User",
            "read_only": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "current_approval_index",
            "label": "Current Approval Step",
            "fieldtype": "Int",
            "read_only": 1,
            "hidden": 1,
            "default": "0",
        },
        {
            "fieldname": "approval_flow",
            "label": "Approval Flow",
            "fieldtype": "Table",
            "options": "Chundakadan Approval Detail",
            "read_only": 1,
        },
    ]

    created = 0
    for dt, _amount_field, insert_after in _APPROVAL_DOCTYPES:
        if not frappe.db.exists("DocType", dt):
            print(f"chundakadan.install: DocType '{dt}' not found, skipping")
            continue

        prev = insert_after
        for spec in common_fields:
            field_spec = {**spec, "insert_after": prev}
            cf_name = f"{dt}-{spec['fieldname']}"
            prev = spec["fieldname"]  # chain so order is preserved

            if frappe.db.exists("Custom Field", cf_name):
                continue
            try:
                frappe.get_doc({
                    "doctype": "Custom Field",
                    "dt": dt,
                    "module": "Chundakadan",
                    "translatable": 0,
                    **field_spec,
                }).insert(ignore_permissions=True)
                created += 1
            except Exception as e:
                print(f"chundakadan.install: could not create {cf_name}: {e}")

    # Threshold field on Chundakadan Settings
    if frappe.db.exists("DocType", "Chundakadan Settings"):
        threshold_cf = "Chundakadan Settings-expense_approval_threshold"
        if not frappe.db.exists("Custom Field", threshold_cf):
            try:
                frappe.get_doc({
                    "doctype": "Custom Field",
                    "dt": "Chundakadan Settings",
                    "module": "Chundakadan",
                    "translatable": 0,
                    "fieldname": "expense_approval_threshold",
                    "label": "Expense Approval Threshold (₹)",
                    "fieldtype": "Currency",
                    "default": "5000",
                    "insert_after": "payroll_basis",
                    "description": (
                        "Above this amount, expense claims / employee advances "
                        "/ payment requests need both Accounts Manager AND GM "
                        "approval. At-or-below, only Accounts Manager is needed."
                    ),
                }).insert(ignore_permissions=True)
                created += 1
            except Exception as e:
                print(f"chundakadan.install: could not create threshold field: {e}")

        # Backfill the Singleton value
        try:
            settings = frappe.get_single("Chundakadan Settings")
            if not settings.get("expense_approval_threshold"):
                settings.set("expense_approval_threshold", 5000)
                settings.flags.ignore_permissions = True
                settings.save()
        except Exception as e:
            print(f"chundakadan.install: could not backfill threshold: {e}")

    if created:
        frappe.db.commit()
        print(f"chundakadan.install: created {created} approval workflow custom fields")


def ensure_expense_payable_account(*args, **kwargs):
    """Idempotent: ensure `2210 Expense Payable` exists per company as
    a plain Liability account (account_type='' — NOT 'Payable').

    Used by the Office Expense Voucher as the deferred-payment Cr
    target. With account_type=Payable, every GL entry would need a
    Supplier party and the bills would pollute the Accounts Payable /
    Aging reports. We want a neutral liability bucket instead.
    """
    import frappe

    for co in frappe.get_all("Company", fields=["name", "abbr"]):
        abbr = co["abbr"]
        full = f"2210 - Expense Payable - {abbr}"
        if frappe.db.exists("Account", full):
            # Normalize account_type: must be '' (not 'Payable')
            current_type = frappe.db.get_value(
                "Account", full, "account_type") or ""
            if current_type == "Payable":
                frappe.db.set_value(
                    "Account", full, "account_type", "",
                    update_modified=False)
                print(f"chundakadan.install: cleared account_type='Payable' "
                      f"on '{full}' (now neutral Liability)")
            continue

        # Prefer `Current Liabilities` as the parent group — sits right
        # above Accounts Payable in standard ERPNext CoAs.
        parent_name = None
        for pattern in ("Current Liabilities", "Accounts Payable"):
            row = frappe.db.sql(
                """
                SELECT name FROM `tabAccount`
                WHERE company = %s
                  AND is_group = 1
                  AND root_type = 'Liability'
                  AND account_name = %s
                LIMIT 1
                """,
                (co["name"], pattern),
                as_dict=True,
            )
            if row:
                parent_name = row[0]["name"]
                break
        if not parent_name:
            row = frappe.db.sql(
                """SELECT name FROM `tabAccount`
                   WHERE company = %s AND is_group = 1 AND root_type = 'Liability'
                   ORDER BY lft LIMIT 1""",
                (co["name"],), as_dict=True,
            )
            parent_name = row[0]["name"] if row else None
        if not parent_name:
            print(f"chundakadan.install: no Liability parent for {co['name']}, "
                  f"skipping Expense Payable creation")
            continue

        # Try 2210, then 2211..2299 if number's taken (some installs put
        # Stock Received But Not Billed at 2210, which conflicts).
        chosen_number = None
        for candidate in ["2210"] + [str(n) for n in range(2211, 2300)]:
            in_use = frappe.db.get_value(
                "Account",
                {"account_number": candidate, "company": co["name"]},
                "name",
            )
            if not in_use:
                chosen_number = candidate
                break

        try:
            doc = frappe.get_doc({
                "doctype": "Account",
                "account_name": "Expense Payable",
                "account_number": chosen_number,  # may be None if 2210-2299 all used
                "parent_account": parent_name,
                "is_group": 0,
                "root_type": "Liability",
                "report_type": "Balance Sheet",
                # account_type intentionally LEFT BLANK — see docstring.
                "company": co["name"],
            })
            doc.flags.ignore_permissions = True
            doc.insert()
            print(f"chundakadan.install: created '{doc.name}'")
        except Exception as e:
            print(f"chundakadan.install: could not create '{full}': {e}")

    frappe.db.commit()


def ensure_oev_settings_fields(*args, **kwargs):
    """Idempotent: add a Table Custom Field on Chundakadan Settings —
    `oev_defaults` — holding per-company defaults for Office Expense
    Voucher (Paid From / Payable Account / Cost Center).

    Multi-company aware: each row pins defaults to one Company.
    Migrate any pre-existing single-value fields into the table on
    first run (they're hidden afterwards).
    """
    import frappe

    if not frappe.db.exists("DocType", "Chundakadan Settings"):
        return

    # --- Step 1: ensure the Table custom field exists ----------------
    table_cf_spec = {
        "fieldname": "oev_defaults",
        "label": "Office Expense Voucher Defaults (per company)",
        "fieldtype": "Table",
        "options": "Chundakadan OEV Default",
        "insert_after": "expense_approval_threshold",
        "description": (
            "Per-company defaults for new Office Expense Vouchers. "
            "When a user creates an OEV for a given company, the row "
            "matching that company auto-fills Paid From / Payable "
            "Account / Cost Center on the form."
        ),
    }
    section_cf_spec = {
        "fieldname": "oev_section",
        "label": "Office Expense Voucher Defaults",
        "fieldtype": "Section Break",
        "insert_after": "expense_approval_threshold",
        "collapsible": 1,
    }

    created = 0
    for spec in (section_cf_spec, table_cf_spec):
        cf_name = f"Chundakadan Settings-{spec['fieldname']}"
        if frappe.db.exists("Custom Field", cf_name):
            continue
        try:
            frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "Chundakadan Settings",
                "module": "Chundakadan",
                "translatable": 0,
                **spec,
            }).insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            print(f"chundakadan.install: could not create {cf_name}: {e}")

    # --- Step 2: hide the old single-value fields (if they exist) -----
    for old in ("oev_default_paid_from",
                "oev_default_payable_account",
                "oev_default_cost_center"):
        cf_name = f"Chundakadan Settings-{old}"
        if frappe.db.exists("Custom Field", cf_name):
            try:
                frappe.db.set_value(
                    "Custom Field", cf_name, "hidden", 1,
                    update_modified=False)
            except Exception:
                pass

    if created:
        frappe.db.commit()
        print(f"chundakadan.install: created {created} OEV settings fields")

    # --- Step 3: seed per-company rows from old singles OR best guess --
    try:
        settings = frappe.get_single("Chundakadan Settings")
        existing_rows = {(r.company or "") for r in (settings.oev_defaults or [])}

        # Pick old singles if they exist (one-time migration)
        old_paid_from = settings.get("oev_default_paid_from")
        old_payable = settings.get("oev_default_payable_account")
        old_cc = settings.get("oev_default_cost_center")

        changed = False
        for co in frappe.get_all("Company", fields=["name", "abbr",
                                                      "cost_center"]):
            if co["name"] in existing_rows:
                continue
            abbr = co["abbr"]
            # Best guess defaults for THIS company
            bank = frappe.db.get_value(
                "Account",
                {"company": co["name"], "is_group": 0,
                 "account_type": "Bank", "disabled": 0},
                "name",
            )
            payable_candidate = f"2210 - Expense Payable - {abbr}"
            payable = payable_candidate if frappe.db.exists(
                "Account", payable_candidate) else None
            cc = co["cost_center"] or frappe.db.get_value(
                "Cost Center",
                {"company": co["name"], "is_group": 0, "disabled": 0},
                "name",
            )

            # First company: prefer migrating old single-value defaults
            # IF they match this company; otherwise use guesses.
            settings.append("oev_defaults", {
                "company": co["name"],
                "paid_from": (old_paid_from
                              if old_paid_from and old_paid_from.endswith(f"- {abbr}")
                              else bank),
                "payable_account": (old_payable
                                    if old_payable and old_payable.endswith(f"- {abbr}")
                                    else payable),
                "cost_center": (old_cc
                                if old_cc and old_cc.endswith(f"- {abbr}")
                                else cc),
            })
            changed = True

        if changed:
            settings.flags.ignore_permissions = True
            settings.save()
            frappe.db.commit()
            n = len(settings.oev_defaults or [])
            print(f"chundakadan.install: seeded {n} per-company OEV "
                  f"default rows")
    except Exception as e:
        print(f"chundakadan.install: could not seed OEV per-company "
              f"defaults: {e}")


def get_oev_defaults_for_company(company: str) -> dict:
    """Helper: resolve OEV defaults for a given company from Chundakadan
    Settings child table. Returns {paid_from, payable_account, cost_center}
    or empty dict if no row matches."""
    import frappe
    if not company or not frappe.db.exists("DocType", "Chundakadan Settings"):
        return {}
    settings = frappe.get_cached_doc("Chundakadan Settings")
    for row in (settings.get("oev_defaults") or []):
        if row.get("company") == company:
            return {
                "paid_from": row.get("paid_from"),
                "payable_account": row.get("payable_account"),
                "cost_center": row.get("cost_center"),
            }
    return {}


def ensure_oev_default_supplier(*args, **kwargs):
    """Idempotent: create a 'Misc Office Expenses' Supplier used as the
    default party on Office Expense Vouchers when the bill has no real
    vendor (e.g. petty cash, ad-hoc reimbursements).

    Idempotency check uses `supplier_name` not docname — Buying Settings
    autoname via Naming Series means the actual docname is e.g.
    'CA-SUPP-00031', not 'Misc Office Expenses'.
    """
    import frappe

    target_name = "Misc Office Expenses"
    existing = frappe.db.get_value(
        "Supplier", {"supplier_name": target_name}, "name")
    if existing:
        return  # already exists, skip

    # Pick any leaf Supplier Group (ERPNext seeds at least one on Company setup)
    sg = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
    if not sg:
        print("chundakadan.install: no leaf Supplier Group found, "
              "skipping default supplier creation")
        return

    try:
        doc = frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": target_name,
            "supplier_group": sg,
            "supplier_type": "Individual",
            "country": "India",
        })
        doc.flags.ignore_permissions = True
        doc.insert()
        frappe.db.commit()
        print(f"chundakadan.install: created Supplier "
              f"'{target_name}' (docname: {doc.name})")
    except Exception as e:
        print(f"chundakadan.install: could not create Supplier "
              f"'{target_name}': {e}")


def ensure_oev_workspace_pin(*args, **kwargs):
    """Idempotent: pin 'Office Expense Voucher' in BOTH workspaces the
    user navigates through — the standard 'Accounting' workspace AND
    the custom 'Chundakadan' workspace (which is where the breadcrumb
    points by default for this install).
    """
    import frappe

    if not frappe.db.exists("DocType", "Office Expense Voucher"):
        return

    for ws_name in ("Accounting", "Chundakadan"):
        if not frappe.db.exists("Workspace", ws_name):
            continue
        _pin_oev_in_workspace(ws_name)


def _pin_oev_in_workspace(ws_name: str) -> None:
    import frappe

    ws = frappe.get_doc("Workspace", ws_name)
    changed = False

    # Shortcut tile
    has_shortcut = any(
        (s.link_to == "Office Expense Voucher" and s.type == "DocType")
        for s in (ws.shortcuts or [])
    )
    if not has_shortcut:
        ws.append("shortcuts", {
            "label": "Office Expense Voucher",
            "type": "DocType",
            "link_to": "Office Expense Voucher",
            "color": "Yellow",
        })
        changed = True

    # Card link under a 'Chundakadan Vouchers' break
    has_link = any(
        (l.link_to == "Office Expense Voucher" and l.type == "Link")
        for l in (ws.links or [])
    )
    if not has_link:
        has_break = any(
            (l.type == "Card Break" and l.label == "Chundakadan Vouchers")
            for l in (ws.links or [])
        )
        if not has_break:
            ws.append("links", {
                "label": "Chundakadan Vouchers",
                "type": "Card Break",
                "icon": "non-profit",
            })
        ws.append("links", {
            "label": "Office Expense Voucher",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "Office Expense Voucher",
        })
        changed = True

    if changed:
        try:
            ws.flags.ignore_permissions = True
            ws.save()
            frappe.db.commit()
            print(f"chundakadan.install: pinned 'Office Expense Voucher' "
                  f"on '{ws_name}' workspace")
        except Exception as e:
            print(f"chundakadan.install: could not pin OEV on "
                  f"'{ws_name}': {e}")


def ensure_je_oev_reference_option(*args, **kwargs):
    """Add 'Office Expense Voucher' to Journal Entry Account.reference_type
    Select options so the Make Payment JV can reference the OEV that
    triggered it (for the on_submit/on_cancel status sync hook).

    Idempotent — patches the existing options string only if OEV
    isn't already in it.
    """
    import frappe

    df = frappe.get_meta("Journal Entry Account").get_field("reference_type")
    if not df:
        return
    options = df.options or ""
    if "Office Expense Voucher" in options.split("\n"):
        return  # already present

    new_options = options.rstrip("\n") + "\nOffice Expense Voucher"
    ps_name = "Journal Entry Account-reference_type-options"

    try:
        if frappe.db.exists("Property Setter", ps_name):
            frappe.db.set_value("Property Setter", ps_name, "value",
                                new_options, update_modified=False)
        else:
            frappe.get_doc({
                "doctype": "Property Setter",
                "doctype_or_field": "DocField",
                "doc_type": "Journal Entry Account",
                "field_name": "reference_type",
                "property": "options",
                "property_type": "Text",
                "value": new_options,
            }).insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.clear_cache(doctype="Journal Entry Account")
        print("chundakadan.install: added 'Office Expense Voucher' to "
              "Journal Entry Account.reference_type options")
    except Exception as e:
        print(f"chundakadan.install: could not patch JE reference_type: {e}")


def ensure_employee_advance_defaults(*args, **kwargs):
    """Tick 'Repay Unclaimed Amount from Salary' by default on Employee
    Advance — unclaimed advances should be recovered automatically
    instead of being written off.

    Uses a Property Setter (not a Custom Field) so the override sits
    on ERPNext's standard field. Idempotent.
    """
    import frappe

    if not frappe.db.exists("DocType", "Employee Advance"):
        return

    ps_name = "Employee Advance-repay_unclaimed_amount_from_salary-default"
    if frappe.db.exists("Property Setter", ps_name):
        # Make sure the value is the one we want — someone might have
        # toggled it back manually
        ps = frappe.get_doc("Property Setter", ps_name)
        if ps.value != "1":
            ps.value = "1"
            ps.save(ignore_permissions=True)
            frappe.db.commit()
            print("chundakadan.install: Property Setter "
                  f"{ps_name} set to '1'")
        return

    try:
        frappe.get_doc({
            "doctype": "Property Setter",
            "doctype_or_field": "DocField",
            "doc_type": "Employee Advance",
            "field_name": "repay_unclaimed_amount_from_salary",
            "property": "default",
            "property_type": "Text",
            "value": "1",
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        print("chundakadan.install: enabled "
              "'Repay Unclaimed Amount from Salary' by default on "
              "Employee Advance")
    except Exception as e:
        print(f"chundakadan.install: could not set default on "
              f"repay_unclaimed_amount_from_salary: {e}")


def ensure_payroll_entry_form_defaults(*args, **kwargs):
    """Two Payroll Entry form tweaks for Chundakadan:

      1. Hide `salary_slip_based_on_timesheet` — Chundakadan doesn't
         use timesheets for salary computation (Fixed-30-Days basis +
         static earnings, see [[project-chundakadan-hr-payroll]]).
         Leaving the box visible just tempts HR to tick it and break
         the payroll run.

      2. Default `payroll_frequency` to "Monthly" — every Chundakadan
         run is monthly. Forcing HR to pick it each time wastes a click
         and risks them picking the wrong frequency.

    Both via Property Setters on the standard HRMS doctype — no schema
    changes, no fork. Idempotent.
    """
    import frappe

    if not frappe.db.exists("DocType", "Payroll Entry"):
        return

    setters = [
        {
            "doc_type": "Payroll Entry",
            "field_name": "salary_slip_based_on_timesheet",
            "property": "hidden",
            "property_type": "Check",
            "value": "1",
        },
        {
            "doc_type": "Payroll Entry",
            "field_name": "payroll_frequency",
            "property": "default",
            "property_type": "Text",
            "value": "Monthly",
        },
    ]

    for ps in setters:
        ps_name = (f"{ps['doc_type']}-{ps['field_name']}"
                   f"-{ps['property']}")
        if frappe.db.exists("Property Setter", ps_name):
            # Update value if it drifted
            cur = frappe.db.get_value("Property Setter", ps_name, "value")
            if cur != ps["value"]:
                frappe.db.set_value("Property Setter", ps_name, "value",
                                     ps["value"], update_modified=False)
                print(f"chundakadan.install: updated PS {ps_name} "
                      f"({cur!r} → {ps['value']!r})")
            continue
        try:
            frappe.get_doc({
                "doctype": "Property Setter",
                "doctype_or_field": "DocField",
                **ps,
            }).insert(ignore_permissions=True)
            print(f"chundakadan.install: created PS {ps_name} "
                  f"= {ps['value']!r}")
        except Exception as e:
            print(f"chundakadan.install: could not create {ps_name}: "
                  f"{str(e)[:120]}")

    frappe.db.commit()
    frappe.clear_cache(doctype="Payroll Entry")


def ensure_employee_transfer_custom_fields(*args, **kwargs):
    """Add `custom_transfer_type` Select + `custom_transfer_remarks`
    on Employee Transfer.

    The transfer_type drives the chundakadan side-effect engine in
    doc_events.employee_transfer.apply_chundakadan_side_effects —
    deciding whether to create/disable Sales Person, add/remove MOP
    mapping, set/clear shift_location, switch Salary Structure, etc.

    Idempotent. Skipped if HRMS Employee Transfer doctype is absent.
    """
    import frappe

    if not frappe.db.exists("DocType", "Employee Transfer"):
        return

    fields = [
        {
            "fieldname": "custom_transfer_type",
            "label": "Transfer Type",
            "fieldtype": "Select",
            "options": "\nTo Sales & Marketing\nFrom Sales & Marketing\n"
                       "Office to Office\nCompany Change\nOther",
            "insert_after": "department",
            "description": "Auto-detected from department change. Drives "
                           "Sales Person, MOP Mapping, Shift Location and "
                           "Salary Structure side-effects on submit.",
            "read_only": 0,
            "in_standard_filter": 1,
        },
        {
            "fieldname": "custom_transfer_remarks",
            "label": "Internal Transfer Notes",
            "fieldtype": "Small Text",
            "insert_after": "custom_transfer_type",
            "description": "HR-internal notes — not shown to the employee.",
        },
    ]

    created = 0
    for cf in fields:
        cf_name = f"Employee Transfer-{cf['fieldname']}"
        if frappe.db.exists("Custom Field", cf_name):
            continue
        try:
            frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "Employee Transfer",
                **cf,
            }).insert(ignore_permissions=True)
            created += 1
            print(f"chundakadan.install: created Custom Field "
                  f"Employee Transfer.{cf['fieldname']}")
        except Exception as e:
            print(f"chundakadan.install: could not create "
                  f"{cf_name}: {e}")
    if created:
        frappe.db.commit()
        frappe.clear_cache(doctype="Employee Transfer")
