# Payroll rebuild — full destructive cleanup + canonical re-seeding.
#
# Confirmed by Najeeb 2026-06-06:
#   - DELETE all existing Salary Slips + linked JVs + SSAs + Structures
#   - Vysakh T + Vishnu S = new SOUTH BDEs (create Employee records)
#   - Unaiz + Soorya Sri = resigned (skip)
#   - ESIC + EPFO BOTH registered → enable correct deduction formulas
#
# DO NOT wire into before_migrate — these functions are destructive.
# Call each phase manually from bench console after reviewing the
# output of the prior phase.
#
# Usage:
#   from chundakadan.seed.payroll_rebuild import *
#   backup_state()                  # phase 0 — save current to JSON
#   cleanup_all_payroll()           # phase 1 — DESTRUCTIVE
#   seed_salary_components()        # phase 2 — fix ESI/PF formulas
#   seed_salary_structures()        # phase 3 — create 4 structures
#   create_missing_employees()      # phase 4 — Vysakh T + Vishnu S
#   recreate_ssas_from_backup()     # phase 5 — restore base salaries

import json
import os
from datetime import datetime

import frappe


COMPANY = "Chundakadan Agencies"
SSA_FROM_DATE = "2026-05-01"          # so May becomes first proper payroll month
BACKUP_DIR = "/tmp/chundakadan_payroll_backup"


# ═════════════════════════════════════════════════════════════════════
# PHASE 0 — BACKUP (read-only)
# ═════════════════════════════════════════════════════════════════════

def backup_state():
    """Snapshot the current payroll state to JSON so we can recreate
    SSAs with the same base salaries after cleanup."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = f"{BACKUP_DIR}/backup_{ts}.json"

    payload = {
        "ts": ts,
        "salary_slips": frappe.get_all(
            "Salary Slip",
            fields=["name", "employee", "start_date", "end_date",
                    "salary_structure", "gross_pay", "net_pay",
                    "docstatus", "journal_entry"],
            limit_page_length=10000,
        ),
        "ssas": frappe.get_all(
            "Salary Structure Assignment",
            fields=["name", "employee", "salary_structure", "base",
                    "from_date", "docstatus", "variable", "currency"],
            limit_page_length=10000,
        ),
        "salary_structures": frappe.get_all(
            "Salary Structure",
            fields=["name", "is_active", "company"],
            limit_page_length=1000,
        ),
        "linked_jvs": list(set(
            s["journal_entry"]
            for s in frappe.get_all(
                "Salary Slip",
                fields=["journal_entry"],
                filters={"journal_entry": ["!=", ""]},
                limit_page_length=10000,
            )
            if s["journal_entry"]
        )),
    }

    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(f"✓ Backup saved: {path}")
    print(f"  Salary Slips:   {len(payload['salary_slips'])}")
    print(f"  SSAs:           {len(payload['ssas'])}")
    print(f"  Structures:     {len(payload['salary_structures'])}")
    print(f"  Linked JVs:     {len(payload['linked_jvs'])}")
    return path


def _latest_backup():
    """Find the most recent backup JSON."""
    if not os.path.isdir(BACKUP_DIR):
        return None
    files = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_")],
        reverse=True,
    )
    return f"{BACKUP_DIR}/{files[0]}" if files else None


# ═════════════════════════════════════════════════════════════════════
# PHASE 1 — DESTRUCTIVE CLEANUP
# ═════════════════════════════════════════════════════════════════════

def cleanup_all_payroll():
    """Cancel + delete in reverse-dependency order:
      1. Journal Entries linked to Salary Slips
      2. Salary Slips (submitted then drafts)
      3. Salary Structure Assignments
      4. Salary Structures

    Requires a backup file in /tmp/chundakadan_payroll_backup/ — call
    backup_state() first."""

    if not _latest_backup():
        raise RuntimeError(
            "No backup found in /tmp/chundakadan_payroll_backup/. "
            "Run backup_state() first."
        )

    print(f"Using backup: {_latest_backup()}")

    counts = {"jvs": 0, "slips": 0, "ssas": 0, "structures": 0}

    # 1. Journal Entries
    linked_jvs = [
        s["journal_entry"]
        for s in frappe.get_all("Salary Slip",
            fields=["journal_entry"],
            filters={"journal_entry": ["!=", ""]},
            limit_page_length=10000)
        if s["journal_entry"]
    ]
    for jv in set(linked_jvs):
        try:
            doc = frappe.get_doc("Journal Entry", jv)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Journal Entry", jv,
                              ignore_permissions=True, force=1)
            counts["jvs"] += 1
        except Exception as e:
            print(f"  ✗ JV {jv}: {e}")
    print(f"  ✓ Journal Entries: {counts['jvs']} deleted")

    # 2. Salary Slips
    for s in frappe.get_all("Salary Slip", fields=["name", "docstatus"],
                            limit_page_length=10000):
        try:
            if s["docstatus"] == 1:
                doc = frappe.get_doc("Salary Slip", s["name"])
                doc.cancel()
            frappe.delete_doc("Salary Slip", s["name"],
                              ignore_permissions=True, force=1)
            counts["slips"] += 1
        except Exception as e:
            print(f"  ✗ Slip {s['name']}: {e}")
    print(f"  ✓ Salary Slips: {counts['slips']} deleted")

    # 3. Salary Structure Assignments
    for s in frappe.get_all("Salary Structure Assignment",
                            fields=["name", "docstatus"],
                            limit_page_length=10000):
        try:
            if s["docstatus"] == 1:
                doc = frappe.get_doc("Salary Structure Assignment", s["name"])
                doc.cancel()
            frappe.delete_doc("Salary Structure Assignment", s["name"],
                              ignore_permissions=True, force=1)
            counts["ssas"] += 1
        except Exception as e:
            print(f"  ✗ SSA {s['name']}: {e}")
    print(f"  ✓ SSAs: {counts['ssas']} deleted")

    # 4. Salary Structures — cancel if submitted before delete
    for s in frappe.get_all("Salary Structure",
                            fields=["name", "docstatus"],
                            limit_page_length=1000):
        try:
            if s.get("docstatus") == 1:
                doc = frappe.get_doc("Salary Structure", s["name"])
                doc.cancel()
            frappe.delete_doc("Salary Structure", s["name"],
                              ignore_permissions=True, force=1)
            counts["structures"] += 1
        except Exception as e:
            print(f"  ✗ Structure {s['name']}: {e}")
    print(f"  ✓ Salary Structures: {counts['structures']} deleted")

    frappe.db.commit()
    return counts


# ═════════════════════════════════════════════════════════════════════
# PHASE 2 — FIX SALARY COMPONENT FORMULAS
# ═════════════════════════════════════════════════════════════════════

def _get_ceilings():
    """Read ESI + PF wage ceilings from Chundakadan Settings.

    Returns (esi_ceiling, esi_extended_ceiling, pf_ceiling).
    Falls back to defaults if fields don't exist yet (first-run
    race condition). HR can change values via the desk + re-run
    seed_salary_components() to propagate.
    """
    esi = frappe.db.get_single_value(
        "Chundakadan Settings", "esi_wage_ceiling") or 21000
    esi_ext = frappe.db.get_single_value(
        "Chundakadan Settings", "esi_extended_ceiling") or 42000
    pf = frappe.db.get_single_value(
        "Chundakadan Settings", "pf_wage_ceiling") or 15000
    return int(esi), int(esi_ext), int(pf)


def _esi_formula(rate):
    """Build the Chundakadan-specific 3-tier ESI formula.

    ESI Base = (Basic + DA) × payment_days / total_working_days

    Per Najeeb's voice clarification 2026-06-06:
      - ESI EXCLUDES Travel Allowance, House Rent Allowance, Food Allowance
      - ESI base = Basic + DA only
      - Arrears + Incentives also excluded (typical, separate from Basic)

    We approximate "Basic + DA" with the SSA `base` field — in chundakadan's
    setup, the `base` salary represents Basic-equivalent. DA is configured
    as a separate component but typically ₹0; HR can add it via DA
    Salary Component if/when it becomes part of the structure.

    LOP handling: multiply by payment_days/total_working_days ratio so
    ESI prorates with attendance (standard Indian practice — ESI on
    actually-paid wages).

    3-tier rule:
      esi_base > 42K (extended_ceiling)  → no ESI
      21K < esi_base ≤ 42K               → ESI on capped 21K
      esi_base ≤ 21K                     → ESI on esi_base directly
    """
    esi_ceiling, esi_ext, _ = _get_ceilings()
    # esi_base = (Basic + DA) prorated; use `base` (SSA base) as proxy
    return (
        f"(lambda esi_base: "
        f"0 if esi_base > {esi_ext} "
        f"else (round({esi_ceiling} * {rate}) if esi_base > {esi_ceiling} "
        f"else round(max(esi_base, 0) * {rate})))"
        f"(base * payment_days / total_working_days)"
    )


def _components_spec():
    """Build the SALARY_COMPONENTS list with current ceilings baked
    into formulas. Called at seed time so the formulas reflect the
    latest Chundakadan Settings values."""
    esi_ceiling, esi_ext, pf_ceiling = _get_ceilings()
    print(f"  Using ESI ceiling = ₹{esi_ceiling:,}, "
          f"ESI extended cutoff = ₹{esi_ext:,}, "
          f"PF ceiling = ₹{pf_ceiling:,}")

    return [
    # ─── Earnings (all static — depends_on_payment_days=0) ────────
    # Static earnings + separate LOP Deduction line matches Chundakadan's
    # May 2026 Excel layout. Najeeb 2026-06-06: "Basic stays at full ₹X,
    # LOP appears as separate column. ESI on Basic+DA only."
    {"salary_component": "Basic", "type": "Earning",
     "depends_on_payment_days": 0},
    {"salary_component": "House Rent Allowance", "type": "Earning",
     "depends_on_payment_days": 0},
    {"salary_component": "Travel Allowance", "type": "Earning",
     "depends_on_payment_days": 0},
    {"salary_component": "Food Allowance", "type": "Earning",
     "depends_on_payment_days": 0},
    {"salary_component": "Dearness Allowance", "type": "Earning",
     "depends_on_payment_days": 0},
    {"salary_component": "Special Allowance", "type": "Earning",
     "depends_on_payment_days": 0},
    {"salary_component": "Medical  Allowance", "type": "Earning",
     "depends_on_payment_days": 0},
    # Abbreviations pinned because the ESI formula references AR/IN/CI
    # by name to subtract their amounts from gross_pay. Without explicit
    # abbrs, Frappe auto-generates from initials and could collide.
    {"salary_component": "Incentive", "type": "Earning",
     "salary_component_abbr": "IN",
     "depends_on_payment_days": 0, "is_additional_component": 1},
    {"salary_component": "Collection Incentive", "type": "Earning",
     "salary_component_abbr": "CI",
     "depends_on_payment_days": 0, "is_additional_component": 1},
    {"salary_component": "Arrear", "type": "Earning",
     "salary_component_abbr": "AR",
     "depends_on_payment_days": 0, "is_additional_component": 1},

    # ─── Statistical (employer contributions, NOT deducted) ───────
    # ESI Employer = 3.25% on (Basic+DA prorated). PF Employer = 12%
    # of min(Basic+DA prorated, ₹15K). Both follow same proration as
    # the corresponding employee deduction.
    {"salary_component": "ESI Employer Contribution", "type": "Earning",
     "statistical_component": 1, "do_not_include_in_total": 1,
     "amount_based_on_formula": 1,
     "formula": _esi_formula(0.0325),
     "round_to_the_nearest_integer": 1,
     "depends_on_payment_days": 0},
    {"salary_component": "PF Employer Contribution", "type": "Earning",
     "statistical_component": 1, "do_not_include_in_total": 1,
     "amount_based_on_formula": 1,
     "formula": f"round(min(base * payment_days / total_working_days, {pf_ceiling}) * 0.12)",
     "round_to_the_nearest_integer": 1,
     "depends_on_payment_days": 0},

    # ─── Deductions ───────────────────────────────────────────────
    # LOP Deduction MUST appear first in deductions so its value is
    # available before ESI/PF compute (Frappe evaluates row-by-row).
    # Formula: prorate FULL earnings (gross_pay) by LOP days.
    {"salary_component": "LOP Deduction", "type": "Deduction",
     "amount_based_on_formula": 1,
     "formula": "round(gross_pay * (total_working_days - payment_days) / total_working_days)",
     "round_to_the_nearest_integer": 1,
     "depends_on_payment_days": 0},

    # ESI = 0.75% on (Basic+DA × payment_days/30), with Chundakadan's
    # 3-tier rule. Per Najeeb 2026-06-06: ESI base excludes HRA, Travel,
    # Food. Only Basic+DA. We use `base` (SSA base) as Basic+DA proxy.
    {"salary_component": "ESI", "type": "Deduction",
     "amount_based_on_formula": 1,
     "formula": _esi_formula(0.0075),
     "round_to_the_nearest_integer": 1,
     "depends_on_payment_days": 0},

    # Employee PF = 12% of min(Basic+DA prorated, ₹15K)
    {"salary_component": "Employee PF", "type": "Deduction",
     "amount_based_on_formula": 1,
     "formula": f"round(min(base * payment_days / total_working_days, {pf_ceiling}) * 0.12)",
     "round_to_the_nearest_integer": 1,
     "depends_on_payment_days": 0},

    # Professional Tax — Kerala slabs on base salary. Static (one full
    # PT per month worked).
    {"salary_component": "Professional Tax", "type": "Deduction",
     "amount_based_on_formula": 1,
     "formula": (
         "(base > 12000 and base <= 17999) * 120 + "
         "(base > 18000 and base <= 29999) * 180 + "
         "(base > 30000 and base <= 44999) * 300 + "
         "(base > 45000 and base <= 59999) * 450 + "
         "(base > 60000 and base <= 74999) * 600 + "
         "(base > 75000 and base <= 99999) * 750 + "
         "(base > 100000 and base <= 124999) * 1000 + "
         "(base > 124999) * 1250"
     ),
     "round_to_the_nearest_integer": 1,
     "depends_on_payment_days": 0},

    {"salary_component": "Welfare Fund", "type": "Deduction",
     "depends_on_payment_days": 0},
    {"salary_component": "Employee Advance Recovery", "type": "Deduction",
     "depends_on_payment_days": 0, "is_additional_component": 1},
    {"salary_component": "Bank Return Charges", "type": "Deduction",
     "depends_on_payment_days": 0, "is_additional_component": 1},
    ]


def seed_salary_components():
    """Fix ESI, PF, and other Salary Component formulas. Idempotent.

    Reads ESI + PF wage ceilings dynamically from Chundakadan Settings
    at run time, so HR can change ceilings via desk + re-run this
    function to propagate the new values into all formulas — no code
    redeploy needed.
    """

    # Delete the duplicate "Provident Fund" component if it exists +
    # is unused (only "Employee PF" should remain)
    if frappe.db.exists("Salary Component", "Provident Fund"):
        # Check if any active Salary Structure / Salary Slip references it
        used = frappe.db.exists("Salary Detail",
            {"salary_component": "Provident Fund", "docstatus": ["!=", 2]})
        if not used:
            try:
                frappe.delete_doc("Salary Component", "Provident Fund",
                                  ignore_permissions=True, force=1)
                print("  ✓ deleted duplicate 'Provident Fund' component")
            except Exception as e:
                print(f"  ✗ couldn't delete 'Provident Fund': {e}")
        else:
            print("  ⚠ 'Provident Fund' is referenced elsewhere — kept")

    created, updated, unchanged = 0, 0, 0
    for spec in _components_spec():
        name = spec["salary_component"]
        exists = frappe.db.exists("Salary Component", name)

        if exists:
            doc = frappe.get_doc("Salary Component", name)
            changed = False
            for k, v in spec.items():
                if k == "salary_component": continue
                if doc.get(k) != v:
                    doc.set(k, v)
                    changed = True
            if changed:
                doc.flags.ignore_permissions = True
                doc.save()
                updated += 1
            else:
                unchanged += 1
        else:
            try:
                new = frappe.get_doc({"doctype": "Salary Component", **spec})
                new.flags.ignore_permissions = True
                new.insert()
                created += 1
            except Exception as e:
                print(f"  ✗ couldn't create {name}: {e}")

    frappe.db.commit()
    print(f"  ✓ Salary Components: {created} created, "
          f"{updated} updated, {unchanged} unchanged")


# ═════════════════════════════════════════════════════════════════════
# PHASE 3 — 4 CANONICAL SALARY STRUCTURES
# ═════════════════════════════════════════════════════════════════════

# Each structure: name + earnings + deductions + statistical components.
# `abbr` is the column header on Salary Slip; we accept Frappe defaults.
# Order matters — affects column order on slips.
SALARY_STRUCTURES = [
    {
        "name": "CDN Sales Executive Structure",
        "for": "Sales Executive / BDE / Sales HOD / Sales Admin",
        "earnings": [
            {"salary_component": "Basic", "depends_on_payment_days": 0,
             "amount_based_on_formula": 1, "formula": "base"},
            {"salary_component": "Travel Allowance", "depends_on_payment_days": 0,
             "amount_based_on_formula": 0, "amount": 0},
            {"salary_component": "Food Allowance", "depends_on_payment_days": 0,
             "amount_based_on_formula": 0, "amount": 0},
            {"salary_component": "Collection Incentive", "depends_on_payment_days": 0,
             "amount_based_on_formula": 0, "amount": 0,
             "is_additional_component": 1},
            {"salary_component": "ESI Employer Contribution",
             "statistical_component": 1, "depends_on_payment_days": 0},
            {"salary_component": "PF Employer Contribution",
             "statistical_component": 1, "depends_on_payment_days": 0},
        ],
        "deductions": [
            # LOP Deduction FIRST so it computes before ESI/PF
            {"salary_component": "LOP Deduction", "depends_on_payment_days": 0},
            {"salary_component": "ESI", "depends_on_payment_days": 0},
            {"salary_component": "Employee PF", "depends_on_payment_days": 0},
            {"salary_component": "Professional Tax", "depends_on_payment_days": 0},
            {"salary_component": "Welfare Fund", "depends_on_payment_days": 0,
             "amount_based_on_formula": 0, "amount": 0},
        ],
    },
    {
        "name": "CDN Office Staff Structure",
        "for": "HR / Accounts / Sales Coordinator / Billing / Dispatch / Purchaser",
        "earnings": [
            {"salary_component": "Basic", "depends_on_payment_days": 0,
             "amount_based_on_formula": 1, "formula": "base"},
            {"salary_component": "House Rent Allowance", "depends_on_payment_days": 0,
             "amount_based_on_formula": 1, "formula": "base * 0.4"},
            {"salary_component": "Food Allowance", "depends_on_payment_days": 0,
             "amount_based_on_formula": 0, "amount": 0},
            {"salary_component": "ESI Employer Contribution",
             "statistical_component": 1, "depends_on_payment_days": 0},
            {"salary_component": "PF Employer Contribution",
             "statistical_component": 1, "depends_on_payment_days": 0},
        ],
        "deductions": [
            {"salary_component": "LOP Deduction", "depends_on_payment_days": 0},
            {"salary_component": "ESI", "depends_on_payment_days": 0},
            {"salary_component": "Employee PF", "depends_on_payment_days": 0},
            {"salary_component": "Professional Tax", "depends_on_payment_days": 0},
            {"salary_component": "Welfare Fund", "depends_on_payment_days": 0,
             "amount_based_on_formula": 0, "amount": 0},
        ],
    },
    {
        "name": "CDN Floor Structure",
        "for": "Floor Assistant / Floor Manager / House Keeping",
        "earnings": [
            {"salary_component": "Basic", "depends_on_payment_days": 0,
             "amount_based_on_formula": 1, "formula": "base"},
            {"salary_component": "Food Allowance", "depends_on_payment_days": 0,
             "amount_based_on_formula": 0, "amount": 0},
            {"salary_component": "ESI Employer Contribution",
             "statistical_component": 1, "depends_on_payment_days": 0},
            {"salary_component": "PF Employer Contribution",
             "statistical_component": 1, "depends_on_payment_days": 0},
        ],
        "deductions": [
            {"salary_component": "LOP Deduction", "depends_on_payment_days": 0},
            {"salary_component": "ESI", "depends_on_payment_days": 0},
            {"salary_component": "Employee PF", "depends_on_payment_days": 0},
            {"salary_component": "Professional Tax", "depends_on_payment_days": 0},
            {"salary_component": "Welfare Fund", "depends_on_payment_days": 0,
             "amount_based_on_formula": 0, "amount": 0},
        ],
    },
    {
        "name": "CDN Management Structure",
        "for": "GM / MD / Senior Manager",
        "earnings": [
            {"salary_component": "Basic", "depends_on_payment_days": 0,
             "amount_based_on_formula": 1, "formula": "base"},
            {"salary_component": "House Rent Allowance", "depends_on_payment_days": 0,
             "amount_based_on_formula": 1, "formula": "base * 0.5"},
            {"salary_component": "Travel Allowance", "depends_on_payment_days": 0,
             "amount_based_on_formula": 0, "amount": 0},
            {"salary_component": "PF Employer Contribution",
             "statistical_component": 1, "depends_on_payment_days": 0},
        ],
        "deductions": [
            {"salary_component": "LOP Deduction", "depends_on_payment_days": 0},
            {"salary_component": "Employee PF", "depends_on_payment_days": 0},
            {"salary_component": "Professional Tax", "depends_on_payment_days": 0},
            {"salary_component": "Welfare Fund", "depends_on_payment_days": 0,
             "amount_based_on_formula": 0, "amount": 0},
        ],
    },
]


def seed_salary_structures():
    """Create the 4 canonical Salary Structures. Idempotent — replaces
    existing structure with the same name if it exists."""
    created = 0
    for spec in SALARY_STRUCTURES:
        name = spec["name"]
        if frappe.db.exists("Salary Structure", name):
            frappe.delete_doc("Salary Structure", name,
                              ignore_permissions=True, force=1)

        doc = frappe.get_doc({
            "doctype": "Salary Structure",
            "name": name,
            "company": COMPANY,
            "is_active": "Yes",
            "currency": "INR",
            "payroll_frequency": "Monthly",
            "salary_slip_based_on_timesheet": 0,
            "earnings": [{"doctype": "Salary Detail", **e}
                         for e in spec["earnings"]],
            "deductions": [{"doctype": "Salary Detail", **d}
                           for d in spec["deductions"]],
        })
        doc.flags.ignore_permissions = True
        doc.insert()
        doc.submit()
        created += 1
        print(f"  ✓ {name} ({spec['for']})")

    frappe.db.commit()
    print(f"  Total: {created} Salary Structures created")


# ═════════════════════════════════════════════════════════════════════
# PHASE 4 — CREATE MISSING EMPLOYEES (Vysakh T + Vishnu S)
# ═════════════════════════════════════════════════════════════════════

NEW_EMPLOYEES = [
    {
        "first_name": "Vysakh", "last_name": "T",
        "employee_name": "Vysakh T",
        "gender": "Male",
        "date_of_birth": "1995-01-01",       # placeholder — HR updates
        "date_of_joining": "2026-05-01",     # placeholder
        "company": COMPANY,
        "designation": "Business Development Executive",
        # department + branch intentionally omitted — ERPNext Department
        # naming is hierarchical (e.g. "Sales & Marketing - CA") and varies
        # per install. HR fills these via desk after creation.
        "status": "Active",
        "employment_type": "Full-time",
    },
    {
        "first_name": "Vishnu", "last_name": "S",
        "employee_name": "Vishnu S",
        "gender": "Male",
        "date_of_birth": "1995-01-01",
        "date_of_joining": "2026-05-01",
        "company": COMPANY,
        "designation": "Business Development Executive",
        "status": "Active",
        "employment_type": "Full-time",
    },
]


def create_missing_employees():
    """Create Vysakh T + Vishnu S as new SOUTH BDEs. Placeholder DOB /
    DoJ — HR updates in desk after creation. Idempotent: skips if an
    Active Employee already exists for the given employee_name."""
    created = 0
    for spec in NEW_EMPLOYEES:
        exists = frappe.db.exists("Employee", {
            "employee_name": spec["employee_name"],
            "status": "Active",
        })
        if exists:
            print(f"  · {spec['employee_name']} already exists ({exists})")
            continue
        try:
            doc = frappe.get_doc({"doctype": "Employee", **spec})
            doc.flags.ignore_permissions = True
            doc.flags.ignore_links = True
            doc.flags.ignore_mandatory = True   # placeholder DOB ok
            doc.insert()
            created += 1
            print(f"  ✓ Created {doc.name}: {doc.employee_name}")
        except Exception as e:
            print(f"  ✗ Couldn't create {spec['employee_name']}: {e}")
    frappe.db.commit()
    print(f"  Total: {created} new employees")


# ═════════════════════════════════════════════════════════════════════
# PHASE 5 — RECREATE SSAs FROM BACKUP
# ═════════════════════════════════════════════════════════════════════

# Maps designation patterns → which Salary Structure to assign.
DESIGNATION_TO_STRUCTURE = [
    # (designation substring lowercase, structure name)
    ("general manager",   "CDN Management Structure"),
    ("managing director", "CDN Management Structure"),
    ("md",                "CDN Management Structure"),  # exact "MD" matches
    ("accounts manager",  "CDN Office Staff Structure"),
    ("hr manager",        "CDN Office Staff Structure"),
    ("hr co",             "CDN Office Staff Structure"),
    ("hr ass",            "CDN Office Staff Structure"),
    ("hr cum",            "CDN Office Staff Structure"),
    ("accountant",        "CDN Office Staff Structure"),
    ("purchase",          "CDN Office Staff Structure"),
    ("billing",           "CDN Office Staff Structure"),
    ("dispatch coord",    "CDN Office Staff Structure"),
    ("sales coord",       "CDN Office Staff Structure"),
    ("sales hod",         "CDN Sales Executive Structure"),
    ("marketing manager", "CDN Sales Executive Structure"),
    ("sales & marketing", "CDN Sales Executive Structure"),
    ("sales executive",       "CDN Sales Executive Structure"),
    ("business development",  "CDN Sales Executive Structure"),  # Business Development Executive
    ("bde",                   "CDN Sales Executive Structure"),
    ("floor manager",     "CDN Floor Structure"),
    ("floor asst",        "CDN Floor Structure"),
    ("floor ass",         "CDN Floor Structure"),
    ("floor sup",         "CDN Floor Structure"),
    ("house keeping",     "CDN Floor Structure"),
    ("housekeeping",      "CDN Floor Structure"),
]


def _structure_for(employee_doc):
    """Pick the right Salary Structure based on Employee's designation."""
    designation = (employee_doc.get("designation") or "").lower()
    for pattern, structure_name in DESIGNATION_TO_STRUCTURE:
        if pattern in designation:
            return structure_name
    return None


def recreate_ssas_from_backup():
    """Create one SSA per active Employee. Base salary preserved from
    the most recent backup; if no backup row exists for an employee
    (e.g., new joiners), default to ₹15,000 (HR adjusts later)."""

    backup_path = _latest_backup()
    if not backup_path:
        raise RuntimeError("No backup found. Run backup_state() first.")

    with open(backup_path) as f:
        backup = json.load(f)

    # Most recent submitted SSA base per employee
    backup_base = {}
    for ssa in backup["ssas"]:
        if ssa.get("docstatus") != 1:
            continue
        emp = ssa.get("employee")
        if not emp:
            continue
        backup_base[emp] = float(ssa.get("base") or 0)

    print(f"Loaded {len(backup_base)} base salaries from backup")

    active = frappe.get_all(
        "Employee",
        filters={"status": "Active"},
        fields=["name", "employee_name", "designation",
                "department", "branch", "date_of_joining"],
        limit_page_length=1000,
    )

    created, skipped = 0, []
    for emp in active:
        structure = _structure_for(emp)
        if not structure:
            skipped.append((emp["name"], emp["employee_name"],
                            "no matching structure",
                            emp.get("designation")))
            continue

        base = backup_base.get(emp["name"], 15000)  # ₹15K default
        from_date = SSA_FROM_DATE

        # Skip if joining date is after our SSA_FROM_DATE
        doj = emp.get("date_of_joining")
        if doj and str(doj) > SSA_FROM_DATE:
            from_date = str(doj)

        try:
            doc = frappe.get_doc({
                "doctype": "Salary Structure Assignment",
                "employee": emp["name"],
                "salary_structure": structure,
                "from_date": from_date,
                "base": base,
                "company": COMPANY,
                "currency": "INR",
            })
            doc.flags.ignore_permissions = True
            doc.insert()
            doc.submit()
            created += 1
            print(f"  ✓ {emp['name']:15s} {emp['employee_name'][:28]:28s} "
                  f"{structure[:35]:35s} base=₹{base:>8,.0f}")
        except Exception as e:
            skipped.append((emp["name"], emp["employee_name"], str(e)[:60],
                            emp.get("designation")))

    frappe.db.commit()
    print(f"\n  Created: {created} SSAs")
    if skipped:
        print(f"  Skipped: {len(skipped)}")
        for name, ename, reason, desig in skipped:
            print(f"    {name:15s} {ename[:28]:28s} desig={desig!r:30s} → {reason}")
    return {"created": created, "skipped": skipped}


# ═════════════════════════════════════════════════════════════════════
# CONVENIENCE — run all phases in order
# ═════════════════════════════════════════════════════════════════════

def run_all_phases():
    """Run all 6 phases sequentially. Read-only Phase 0 first; then
    destructive Phase 1; then rebuild Phases 2-5. Print explicit
    confirmation prompts between destructive steps."""
    print("=" * 60)
    print("Phase 0 — Backup current state")
    print("=" * 60)
    backup_state()

    print("\n" + "=" * 60)
    print("Phase 1 — DESTRUCTIVE cleanup (no confirmation prompt — Najeeb pre-approved)")
    print("=" * 60)
    cleanup_all_payroll()

    print("\n" + "=" * 60)
    print("Phase 2 — Fix Salary Component formulas (ESI / PF / etc.)")
    print("=" * 60)
    seed_salary_components()

    print("\n" + "=" * 60)
    print("Phase 3 — Create 4 canonical Salary Structures")
    print("=" * 60)
    seed_salary_structures()

    print("\n" + "=" * 60)
    print("Phase 4 — Create Vysakh T + Vishnu S Employee records")
    print("=" * 60)
    create_missing_employees()

    print("\n" + "=" * 60)
    print("Phase 5 — Recreate SSAs (preserved base salaries)")
    print("=" * 60)
    recreate_ssas_from_backup()

    print("\n" + "=" * 60)
    print("✓ All phases complete. Run a Payroll Entry for May 2026 to verify.")
    print("=" * 60)


# ═════════════════════════════════════════════════════════════════════
# REFRESH — re-apply component formulas + structures after spec edits
# ═════════════════════════════════════════════════════════════════════

def refresh_structures():
    """Hot-update: drop the 4 canonical Salary Structures + recreate
    them with the current SALARY_STRUCTURES spec. Preserves SSAs by
    cancelling them first, deleting + recreating structures, then
    re-creating SSAs from the latest backup.

    Use this when you've edited the SALARY_STRUCTURES or SALARY_COMPONENTS
    spec in payroll_rebuild.py and want existing structures to reflect
    the changes.
    """
    print("Refreshing Salary Components + Structures…\n")

    # 1. Update components first (no structure dependency)
    seed_salary_components()

    # 2. Snapshot current SSAs so we can recreate them
    backup_state()

    # 3. Cancel + delete SSAs (they reference structures by name)
    print("\nCancelling + deleting current SSAs…")
    for s in frappe.get_all("Salary Structure Assignment",
                            fields=["name", "docstatus"],
                            limit_page_length=10000):
        try:
            if s["docstatus"] == 1:
                doc = frappe.get_doc("Salary Structure Assignment", s["name"])
                doc.cancel()
            frappe.delete_doc("Salary Structure Assignment", s["name"],
                              ignore_permissions=True, force=1)
        except Exception as e:
            print(f"  ✗ SSA {s['name']}: {str(e)[:80]}")

    # 4. Cancel + delete the 4 canonical structures
    print("\nCancelling + deleting 4 canonical structures…")
    for spec in SALARY_STRUCTURES:
        if not frappe.db.exists("Salary Structure", spec["name"]):
            continue
        try:
            doc = frappe.get_doc("Salary Structure", spec["name"])
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Salary Structure", spec["name"],
                              ignore_permissions=True, force=1)
            print(f"  ✓ deleted {spec['name']}")
        except Exception as e:
            print(f"  ✗ {spec['name']}: {str(e)[:80]}")

    frappe.db.commit()

    # 5. Recreate structures with new spec
    print("\nRecreating structures with new spec…")
    seed_salary_structures()

    # 6. Recreate SSAs from backup
    print("\nRecreating SSAs from latest backup…")
    recreate_ssas_from_backup()

    print("\n✓ refresh_structures() complete")
