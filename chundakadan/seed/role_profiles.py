# Role Profiles + Module Profiles for Chundakadan Agencies.
#
# 15 canonical profile groups derived from the user permission spreadsheet
# (2026-06-05). Each profile bundles:
#   roles            — what the user can DO (Sales User, HR Manager, etc.)
#   modules_enabled  — which desk modules are VISIBLE to this profile
#                      (everything else gets added to block_modules)
#
# Seeded on every migrate via chundakadan/install.py → before_migrate hook.
# Re-running is idempotent: profiles get their roles + module visibility
# synced to the definitions below.
#
# To assign profiles to users:
#   bench --site <site> execute \
#       chundakadan.seed.role_profiles.apply_user_assignments
#
# That function sets role_profile_name + module_profile on each user AND
# explicitly copies the profile's roles into their Has Role rows
# (Frappe's auto-sync from role_profile_name only fires on change
# detection, so we don't rely on it).

import frappe


# ─────────────────────────────────────────────────────────────────────
# CANONICAL MODULE LIST
# Everything ERPNext + the chundakadan bench exposes. If you install a
# new app, add its module here so it can appear in profile whitelists.
# ─────────────────────────────────────────────────────────────────────

ALL_MODULES = [
    "Accounts", "Assets", "Audit Trail", "Automation",
    "Bulk Transaction", "Buying", "Chundakadan",
    "Communication", "Contacts", "Core", "CRM", "Custom",
    "Datavalue Theme 15", "Desk", "EDI", "Email",
    "ERPNext Integrations", "Field Sales", "Geo",
    "GST India", "HR", "Income Tax India", "Integrations",
    "Maintenance", "Manufacturing", "Payroll",
    "Portal", "Printing", "Projects", "Quality Management",
    "Regional", "Selling", "Setup", "Social", "Stock",
    "Subcontracting", "Support", "Telephony", "Utilities",
    "VAT India", "Website", "Workflow",
]


# Modules that EVERY profile needs (always enabled, no exceptions):
#   Communication, Email, Contacts — basic collaboration
#   Desk, Core, Custom            — Frappe-internal, breaks UI if hidden
#   Chundakadan, Datavalue Theme 15 — our app + theme
_ALWAYS_ENABLED = {
    "Communication", "Email", "Contacts",
    "Desk", "Core", "Custom",
    "Chundakadan", "Datavalue Theme 15",
}


# ─────────────────────────────────────────────────────────────────────
# PROFILE DEFINITIONS
# ─────────────────────────────────────────────────────────────────────

PROFILES = [
    {
        # Sales Executives — mobile-app workflow, minimal desk
        "name": "CDN Sales Executive",
        "roles": [
            "Sales User", "Employee", "Employee Self Service",
            "Stock User", "Accounts User", "Item Manager",
            "Leave Approver",
        ],
        "modules_enabled": [
            "Selling", "Stock", "Accounts", "Field Sales",
            "HR", "Payroll",  # for self-service leave/payslip
        ],
    },
    {
        # House keeping — HR self-service only
        "name": "CDN Mobile HR",
        "roles": [
            "Employee", "Employee Self Service", "HR User",
        ],
        "modules_enabled": [
            "HR", "Payroll", "Field Sales",
        ],
    },
    {
        # Floor assistants — HR + Stock visibility
        "name": "CDN Mobile HR Stock",
        "roles": [
            "Employee", "Employee Self Service", "HR User",
            "Stock User", "Item Manager",
        ],
        "modules_enabled": [
            "HR", "Payroll", "Stock", "Field Sales",
        ],
    },
    {
        # HR Manager (Bindu) — primary HR admin + payroll + banking
        "name": "CDN HR Manager",
        "roles": [
            "HR Manager", "HR User",
            "Stock User", "Accounts User",
            "Newsletter Manager", "Expense Approver",
            "HR Leave Approver", "Leave Approver",
            "Employee", "Employee Self Service",
        ],
        "modules_enabled": [
            "HR", "Payroll", "Accounts", "Stock",
            "Selling", "Buying", "CRM", "Assets",
            "Field Sales", "GST India",
            "Income Tax India", "VAT India",
        ],
    },
    {
        # HR Assistant (Nakshathra) — HR + payroll only
        "name": "CDN HR Assistant",
        "roles": [
            "HR User", "HR Leave Approver", "Leave Approver",
            "Newsletter Manager",
            "Employee", "Employee Self Service",
        ],
        "modules_enabled": [
            "HR", "Payroll", "Field Sales",
        ],
    },
    {
        # Sales HOD / Marketing Manager (Arjun)
        "name": "CDN Sales HOD",
        "roles": [
            "Sales User", "Stock User",
            "Sales HOD Leave Approver", "Leave Approver",
            "Item Manager", "Accounts User",
            "Employee", "Employee Self Service",
        ],
        "modules_enabled": [
            "Selling", "Stock", "CRM", "Field Sales",
            "HR", "Payroll", "GST India",
        ],
    },
    {
        # Deputy Sales & Marketing Admin (Razeel)
        # — full sales admin + cross-department visibility
        "name": "CDN Sales Admin",
        "roles": [
            "Sales User", "Sales Master Manager",
            "Stock User", "Accounts User", "Purchase User",
            "Sales HOD Leave Approver", "Leave Approver",
            "Employee", "Employee Self Service",
        ],
        "modules_enabled": [
            "Selling", "Stock", "Accounts", "Buying",
            "CRM", "Assets", "Field Sales",
            "HR", "Payroll", "GST India",
        ],
    },
    {
        # Accounts Manager (Abdul Rashid)
        "name": "CDN Accounts Manager",
        "roles": [
            "Accounts Manager", "Accounts User",
            "Stock User", "Purchase User", "Sales User",
            "Accounts Manager Leave Approver", "Leave Approver",
            "Employee", "Employee Self Service",
        ],
        "modules_enabled": [
            "Accounts", "Stock", "Selling", "Buying",
            "Assets", "HR", "Payroll", "Field Sales",
            "GST India", "Income Tax India", "VAT India",
        ],
    },
    {
        # Accountant filer (Adarsh) — broad ops, no approver roles
        "name": "CDN Accountant",
        "roles": [
            "Accounts User", "Stock User", "Sales User",
            "Purchase User", "HR User",
            "Employee", "Employee Self Service",
        ],
        "modules_enabled": [
            "Accounts", "Stock", "Selling", "Buying",
            "HR", "Payroll", "Field Sales",
            "GST India", "Income Tax India", "VAT India",
        ],
    },
    {
        # Purchaser (Shahla)
        "name": "CDN Purchaser",
        "roles": [
            "Purchase User", "Stock User", "Accounts User",
            "Employee", "Employee Self Service",
        ],
        "modules_enabled": [
            "Buying", "Stock", "Accounts",
            "HR", "Payroll", "Field Sales",
        ],
    },
    {
        # Billing (Jazeel)
        "name": "CDN Billing",
        "roles": [
            "Sales User", "Stock User",
            "Employee", "Employee Self Service",
        ],
        "modules_enabled": [
            "Selling", "Stock", "HR", "Payroll", "Field Sales",
        ],
    },
    {
        # Dispatch coordinator (Afeefa)
        "name": "CDN Dispatch",
        "roles": [
            "Stock User", "Item Manager",
            "Employee", "Employee Self Service",
        ],
        "modules_enabled": [
            "Stock", "HR", "Payroll", "Field Sales",
        ],
    },
    {
        # Sales Coordinator (Jisna, Saranaya)
        "name": "CDN Sales Coordinator",
        "roles": [
            "Sales User", "Stock User", "HR User",
            "Employee", "Employee Self Service",
        ],
        "modules_enabled": [
            "Selling", "Stock", "CRM", "HR", "Payroll",
            "Field Sales",
        ],
    },
    {
        # Managing Director (Veerankutty) — read-everything overview
        "name": "CDN MD",
        "roles": [
            "Sales Manager", "Stock Manager",
            "Accounts Manager", "Auditor",
            "Newsletter Manager",
            "Employee", "Employee Self Service",
        ],
        "modules_enabled": [
            "Accounts", "Stock", "Selling", "Buying",
            "Assets", "HR", "Payroll", "CRM", "Field Sales",
            "GST India", "Income Tax India", "VAT India",
            "Audit Trail",
        ],
    },
    {
        # General Manager (Najeeb) — system admin
        # Modules matched to Najeeb's spec 2026-06-05.
        "name": "CDN GM",
        "roles": [
            "System Manager", "HR Manager",
            "GM Leave Approver", "Leave Approver",
            "Newsletter Manager",
            "Employee", "Employee Self Service",
        ],
        "modules_enabled": [
            "Accounts", "Assets", "Buying", "CRM",
            "Field Sales", "GST India", "HR", "Payroll",
            "Selling", "Stock",
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────
# USER → PROFILE MAPPING
# ─────────────────────────────────────────────────────────────────────

USER_PROFILE_MAP = {
    # Sales Executives
    "shyamkurian31@gmail.com":        "CDN Sales Executive",
    "shijocs62@gmail.com":            "CDN Sales Executive",
    "sharonmadhu5@gmail.com":         "CDN Sales Executive",
    "ashraf@gmail.com":               "CDN Sales Executive",
    "bipithcherkool13@gmail.com":     "CDN Sales Executive",
    "ashifkr95@gmail.com":            "CDN Sales Executive",
    "anshaf@gmail.com":               "CDN Sales Executive",

    # House keeping
    "animol@gmail.com":               "CDN Mobile HR",
    "nafiya@gmail.com":               "CDN Mobile HR",

    # Floor assistants / manager
    "sreeraj@gmail.com":              "CDN Mobile HR Stock",
    "dishil@gmail.com":               "CDN Mobile HR Stock",
    "ameen@gmail.com":                "CDN Mobile HR Stock",
    "sharafudheen@gmail.com":         "CDN Mobile HR Stock",
    "shabeerali@gmail.com":           "CDN Mobile HR Stock",
    "mvinu994@gmail.com":             "CDN Mobile HR Stock",

    # HR
    "binduudayan334@gmail.com":       "CDN HR Manager",
    "chundakadanadmi@gmail.com":      "CDN HR Manager",

    # Sales HODs
    "marketing@chundakadan.in":       "CDN Sales HOD",
    "sales@chundakadan.in":           "CDN Sales Admin",

    # Accounts + Purchase
    "accounts@chundakadan.in":        "CDN Accounts Manager",
    "acountschundakadan@gmail.com":   "CDN Accountant",
    "purchasechundakadan@gmail.com":  "CDN Purchaser",

    # Billing + Dispatch
    "jazeelchundakadan@gmail.com":    "CDN Billing",
    "afeefachundakadan@gmail.com":    "CDN Dispatch",

    # Sales Coordinators
    "mc.chundakadan@gmail.com":       "CDN Sales Coordinator",
    "saranyachundakadan@gmail.com":   "CDN Sales Coordinator",

    # Leadership
    "md.chundakadan@gmail.com":       "CDN MD",
    "gm@chundakadan.in":              "CDN GM",
}


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────

def _hidden_modules_for(profile):
    """Given a profile spec (whitelist), return the set of modules
    that should appear in block_modules. Subtracts the user-declared
    modules_enabled and the global _ALWAYS_ENABLED set from ALL_MODULES.
    """
    enabled = set(profile.get("modules_enabled", []))
    enabled.update(_ALWAYS_ENABLED)
    return set(ALL_MODULES) - enabled


# ─────────────────────────────────────────────────────────────────────
# SEED FUNCTIONS
# ─────────────────────────────────────────────────────────────────────

def _ensure_role_profile(profile):
    """Idempotent: create or sync a Role Profile to match `profile`."""
    name = profile["name"]
    target_roles = set(profile["roles"])

    if frappe.db.exists("Role Profile", name):
        doc = frappe.get_doc("Role Profile", name)
        existing_roles = {r.role for r in doc.roles}
        if target_roles == existing_roles:
            return "unchanged"
        doc.roles = []
        for role in target_roles:
            doc.append("roles", {"role": role})
        doc.flags.ignore_permissions = True
        doc.save()
        return "updated"

    doc = frappe.get_doc({
        "doctype": "Role Profile",
        "role_profile": name,
        "roles": [{"role": r} for r in target_roles],
    })
    doc.flags.ignore_permissions = True
    doc.insert()
    return "created"


def _ensure_module_profile(profile):
    """Idempotent: create or sync a Module Profile so the modules in
    the profile's `modules_enabled` whitelist are visible and
    everything else in ALL_MODULES is blocked.
    """
    name = profile["name"]
    target_hidden = _hidden_modules_for(profile)

    if frappe.db.exists("Module Profile", name):
        doc = frappe.get_doc("Module Profile", name)
        existing_hidden = {b.module for b in doc.block_modules}
        if target_hidden == existing_hidden:
            return "unchanged"
        doc.block_modules = []
        for mod in target_hidden:
            doc.append("block_modules", {"module": mod})
        doc.flags.ignore_permissions = True
        doc.save()
        return "updated"

    doc = frappe.get_doc({
        "doctype": "Module Profile",
        "module_profile_name": name,
        "block_modules": [{"module": m} for m in target_hidden],
    })
    doc.flags.ignore_permissions = True
    doc.insert()
    return "created"


def seed_profiles():
    """Create all 15 CDN Role Profiles + Module Profiles. Idempotent.
    Returns a per-profile status summary."""
    result = []
    for profile in PROFILES:
        try:
            r_status = _ensure_role_profile(profile)
        except Exception as e:
            r_status = f"error: {e}"[:60]
        try:
            m_status = _ensure_module_profile(profile)
        except Exception as e:
            m_status = f"error: {e}"[:60]
        result.append((profile["name"], r_status, m_status))
    frappe.db.commit()

    created = sum(1 for _, r, _ in result if r == "created")
    updated = sum(1 for _, r, _ in result if r == "updated")
    if created or updated:
        print(
            f"chundakadan.seed.role_profiles: {created} created, "
            f"{updated} updated, "
            f"{len(result) - created - updated} unchanged"
        )
    return result


def apply_user_assignments():
    """Apply USER_PROFILE_MAP — set role_profile_name + module_profile
    + EXPLICITLY copy the profile's roles into the user's Has Role rows.

    Why explicit copy: Frappe's auto-sync from role_profile_name only
    fires on change-detection — if the field was already set, the
    auto-sync skips. So we do it the slow-but-correct way:

      1. Strip every existing Has Role from the user
      2. Add each role from the Role Profile
      3. Save with role_profile_name + module_profile set

    Idempotent. Re-runnable. Safe to call after profile edits to
    propagate role changes to assigned users.
    """
    print(f"Applying profile assignments to {len(USER_PROFILE_MAP)} users…\n")
    applied = []
    skipped = []

    profile_roles_map = {p["name"]: list(p["roles"]) for p in PROFILES}

    for user, profile_name in USER_PROFILE_MAP.items():
        if not frappe.db.exists("User", user):
            skipped.append((user, "user missing"))
            continue
        if not frappe.db.exists("Role Profile", profile_name):
            skipped.append((user, f"profile missing: {profile_name}"))
            continue
        roles_to_apply = profile_roles_map.get(profile_name, [])
        if not roles_to_apply:
            skipped.append((user, f"no roles defined for {profile_name}"))
            continue
        try:
            doc = frappe.get_doc("User", user)
            doc.roles = []
            for role in roles_to_apply:
                doc.append("roles", {"role": role})
            doc.role_profile_name = profile_name
            if frappe.db.exists("Module Profile", profile_name):
                doc.module_profile = profile_name
            doc.flags.ignore_permissions = True
            doc.save()
            applied.append((user, profile_name))
            print(f"  ✓ {user:35s} → {profile_name:25s} ({len(roles_to_apply)} roles)")
        except Exception as e:
            skipped.append((user, str(e)[:80]))
            print(f"  ✗ {user:35s} {str(e)[:80]}")

    frappe.db.commit()
    frappe.clear_cache()
    print(f"\nApplied: {len(applied)} / Skipped: {len(skipped)}")
    if skipped:
        print("\nSkipped detail:")
        for u, *rest in skipped:
            print(f"  {u}: {rest}")
    return {"applied": applied, "skipped": skipped}


def cleanup_unused_profiles():
    """Delete Role Profiles + Module Profiles that aren't referenced by
    any enabled user. Never touches profiles named in our canonical
    PROFILES list, even if they appear unused right now (avoids
    deleting a profile mid-rollout before assignments are applied).
    """
    canonical_names = {p["name"] for p in PROFILES}
    deleted_role, deleted_module = [], []

    for rp_name in frappe.get_all("Role Profile", pluck="name",
                                  ignore_permissions=True):
        if rp_name in canonical_names:
            continue
        in_use = frappe.db.exists(
            "User", {"role_profile_name": rp_name, "enabled": 1}
        )
        if in_use:
            continue
        try:
            frappe.delete_doc(
                "Role Profile", rp_name, ignore_permissions=True, force=1
            )
            deleted_role.append(rp_name)
        except Exception as e:
            print(f"  ✗ could not delete Role Profile '{rp_name}': {e}")

    for mp_name in frappe.get_all("Module Profile", pluck="name",
                                  ignore_permissions=True):
        if mp_name in canonical_names:
            continue
        in_use = frappe.db.exists(
            "User", {"module_profile": mp_name, "enabled": 1}
        )
        if in_use:
            continue
        try:
            frappe.delete_doc(
                "Module Profile", mp_name, ignore_permissions=True, force=1
            )
            deleted_module.append(mp_name)
        except Exception as e:
            print(f"  ✗ could not delete Module Profile '{mp_name}': {e}")

    frappe.db.commit()

    if deleted_role:
        print(f"chundakadan.seed.role_profiles: deleted {len(deleted_role)} "
              f"unused Role Profiles: {deleted_role}")
    if deleted_module:
        print(f"chundakadan.seed.role_profiles: deleted {len(deleted_module)} "
              f"unused Module Profiles: {deleted_module}")

    return deleted_role, deleted_module


def audit():
    """Print current state of all profiles + user assignments."""
    print("=== Role Profiles ===\n")
    for p in PROFILES:
        if not frappe.db.exists("Role Profile", p["name"]):
            print(f"  ✗ MISSING: {p['name']}")
            continue
        doc = frappe.get_doc("Role Profile", p["name"])
        actual = sorted([r.role for r in doc.roles])
        target = sorted(p["roles"])
        match = "✓" if actual == target else "⚠"
        print(f"  {match} {p['name']:30s} ({len(actual)} roles)")
        if actual != target:
            extra = set(actual) - set(target)
            missing = set(target) - set(actual)
            if extra:    print(f"      extra:   {sorted(extra)}")
            if missing:  print(f"      missing: {sorted(missing)}")

    print("\n=== Module Profiles ===\n")
    for p in PROFILES:
        if not frappe.db.exists("Module Profile", p["name"]):
            print(f"  ✗ MISSING: {p['name']}")
            continue
        doc = frappe.get_doc("Module Profile", p["name"])
        target_hidden = _hidden_modules_for(p)
        actual_hidden = {b.module for b in doc.block_modules}
        match = "✓" if actual_hidden == target_hidden else "⚠"
        enabled_n = len(ALL_MODULES) - len(actual_hidden)
        print(f"  {match} {p['name']:30s} ({enabled_n} modules visible)")

    print("\n=== User Assignments ===\n")
    for user, expected in USER_PROFILE_MAP.items():
        if not frappe.db.exists("User", user):
            print(f"  ✗ {user:35s} (user missing)")
            continue
        actual_rp = frappe.db.get_value("User", user, "role_profile_name")
        actual_mp = frappe.db.get_value("User", user, "module_profile")
        rp_match = "✓" if actual_rp == expected else "⚠"
        mp_match = "✓" if actual_mp == expected else "⚠"
        print(f"  {rp_match}{mp_match} {user:35s} {expected}")
