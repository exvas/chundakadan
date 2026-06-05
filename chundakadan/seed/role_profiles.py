# Role Profiles + Module Profiles for Chundakadan Agencies.
#
# 15 canonical profile groups derived from the user permission spreadsheet
# (2026-06-05). Each profile bundles:
#   roles            — what the user can DO (Sales User, HR Manager, etc.)
#   modules_hidden   — what desk modules are HIDDEN from the workspace
#                      sidebar (everything else stays visible)
#
# Seeded on every migrate via chundakadan/install.py → before_migrate hook.
# Re-running is idempotent: existing profiles get their roles + hidden
# modules synced to the definitions below.
#
# To assign profiles to users:
#   bench --site <site> execute \
#       chundakadan.seed.role_profiles.apply_user_assignments
#
# That function uses USER_PROFILE_MAP (below) to set role_profile_name +
# module_profile on each user. Saving a User with role_profile_name set
# triggers Frappe's standard role-sync which copies the profile's roles
# into the user's Has Role rows.

import frappe


# ─────────────────────────────────────────────────────────────────────
# PROFILE DEFINITIONS
# ─────────────────────────────────────────────────────────────────────

PROFILES = [
    {
        # Sales Executives — mobile-app only, no desk login expected
        "name": "CDN Sales Executive",
        "roles": [
            "Sales User", "Employee", "Employee Self Service",
            "Stock User", "Accounts User", "Item Manager",
            "Leave Approver",
        ],
        "modules_hidden": [
            "Buying", "Manufacturing", "Quality Management",
            "Maintenance", "CRM", "Asset", "Projects",
            "Website", "Integrations", "Customization", "Frappe",
            "Build", "Help",
        ],
    },
    {
        # House keeping — mobile + HR self-service only
        "name": "CDN Mobile HR",
        "roles": [
            "Employee", "Employee Self Service", "HR User",
        ],
        "modules_hidden": [
            "Selling", "Buying", "Stock", "Accounts",
            "Manufacturing", "CRM", "Asset", "Projects",
            "Website", "Integrations", "Customization",
            "Quality Management", "Maintenance", "Build", "Help",
        ],
    },
    {
        # Floor assistants — mobile + HR + Stock
        "name": "CDN Mobile HR Stock",
        "roles": [
            "Employee", "Employee Self Service", "HR User",
            "Stock User", "Item Manager",
        ],
        "modules_hidden": [
            "Selling", "Buying", "Accounts",
            "Manufacturing", "CRM", "Asset", "Projects",
            "Website", "Integrations", "Customization",
            "Quality Management", "Maintenance", "Build", "Help",
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
        "modules_hidden": [
            "Manufacturing", "Quality Management", "Maintenance",
            "Projects", "Website", "Build", "Help",
        ],
    },
    {
        # HR Assistant (Nakshathra) — HR + Track + Payroll, no banking
        "name": "CDN HR Assistant",
        "roles": [
            "HR User", "HR Leave Approver", "Leave Approver",
            "Newsletter Manager",
            "Employee", "Employee Self Service",
        ],
        "modules_hidden": [
            "Selling", "Buying", "Stock", "Accounts",
            "Manufacturing", "Maintenance", "Projects",
            "Website", "CRM", "Build", "Help",
        ],
    },
    {
        # Sales HOD / Marketing Manager (Arjun)
        "name": "CDN Sales HOD",
        "roles": [
            "Sales User", "Stock User",
            "Sales HOD Leave Approver", "Leave Approver",
            "Employee", "Employee Self Service",
        ],
        "modules_hidden": [
            "Manufacturing", "Maintenance", "Quality Management",
            "Projects", "Website", "Build", "Help",
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
        "modules_hidden": [
            "Manufacturing", "Maintenance", "Quality Management",
            "Projects", "Website", "Build", "Help",
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
        "modules_hidden": [
            "Manufacturing", "Maintenance", "Quality Management",
            "Projects", "Website", "Build", "Help",
        ],
    },
    {
        # Accountant filer (Adarsh) — broad operational access, no
        # approver roles
        "name": "CDN Accountant",
        "roles": [
            "Accounts User", "Stock User", "Sales User",
            "Purchase User", "HR User",
            "Employee", "Employee Self Service",
        ],
        "modules_hidden": [
            "Manufacturing", "Maintenance", "Quality Management",
            "Projects", "Website", "CRM", "Build", "Help",
        ],
    },
    {
        # Purchaser (Shahla)
        "name": "CDN Purchaser",
        "roles": [
            "Purchase User", "Stock User", "Accounts User",
            "Employee", "Employee Self Service",
        ],
        "modules_hidden": [
            "Selling", "HR", "Manufacturing", "Maintenance",
            "Projects", "Website", "CRM",
            "Quality Management", "Build", "Help",
        ],
    },
    {
        # Billing (Jazeel)
        "name": "CDN Billing",
        "roles": [
            "Sales User", "Stock User",
            "Employee", "Employee Self Service",
        ],
        "modules_hidden": [
            "HR", "Buying", "Manufacturing", "Maintenance",
            "Projects", "Website", "CRM", "Accounts",
            "Quality Management", "Build", "Help",
        ],
    },
    {
        # Dispatch coordinator (Afeefa)
        "name": "CDN Dispatch",
        "roles": [
            "Stock User", "Item Manager",
            "Employee", "Employee Self Service",
        ],
        "modules_hidden": [
            "Selling", "HR", "Accounts", "Manufacturing",
            "Maintenance", "Projects", "Website", "CRM", "Buying",
            "Quality Management", "Build", "Help",
        ],
    },
    {
        # Sales Coordinator (Jisna, Saranaya) — sales + attendance viewing
        "name": "CDN Sales Coordinator",
        "roles": [
            "Sales User", "Stock User", "HR User",
            "Employee", "Employee Self Service",
        ],
        "modules_hidden": [
            "Buying", "Accounts", "Manufacturing", "Maintenance",
            "Projects", "Website", "CRM",
            "Quality Management", "Build", "Help",
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
        "modules_hidden": [
            "Build",  # Frappe-internal, never useful
        ],
    },
    {
        # General Manager (Najeeb) — system admin
        "name": "CDN GM",
        "roles": [
            "System Manager", "HR Manager",
            "GM Leave Approver", "Leave Approver",
            "Newsletter Manager",
            "Employee", "Employee Self Service",
        ],
        "modules_hidden": [
            "Build",  # Frappe-internal, never useful
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
    "chundakadanadmi@gmail.com":      "CDN HR Assistant",

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
# SEED FUNCTIONS
# ─────────────────────────────────────────────────────────────────────

def _ensure_role_profile(profile):
    """Idempotent: create or sync a Role Profile to match `profile`.

    Re-running rewrites the role list to exactly the spec — adds missing
    roles, removes ones not in the spec.
    """
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
    """Idempotent: create or sync a Module Profile to hide the given
    modules from the desk workspace sidebar.
    """
    name = profile["name"]
    target_hidden = set(profile["modules_hidden"])

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

    # One-line status print so the migrate output is informative
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
    """Apply USER_PROFILE_MAP — set role_profile_name + module_profile on
    each user. Saving a User with role_profile_name triggers Frappe's
    standard role-sync (copies profile's roles into the user's Has Role
    rows). Module Profile takes effect on the user's next desk login.

    Run manually after seed_profiles() has populated the profiles:
        bench --site <site> execute \\
            chundakadan.seed.role_profiles.apply_user_assignments
    """
    print(f"Applying profile assignments to {len(USER_PROFILE_MAP)} users…\n")
    applied = []
    skipped = []

    # Cache profile -> roles map so we can copy roles explicitly
    # (Frappe's auto-sync from role_profile_name only fires on CHANGE
    # detection, so re-runs with the same value silently skip the
    # role copy. We do it ourselves to guarantee correctness.)
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

            # 1. Strip ALL existing roles for a clean slate (no leftover
            #    cruft from previous profile assignments, hand-grants,
            #    or fixture imports).
            doc.roles = []

            # 2. Add every role from the profile spec.
            for role in roles_to_apply:
                doc.append("roles", {"role": role})

            # 3. Set profile linkages so the desk shows the relationship.
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
    print(f"\nApplied: {len(applied)} / Skipped: {len(skipped)}")
    if skipped:
        print("\nSkipped detail:")
        for u, reason in skipped:
            print(f"  {u}: {reason}")
    return {"applied": applied, "skipped": skipped}


def cleanup_unused_profiles():
    """Delete Role Profiles + Module Profiles that aren't referenced by
    any enabled user. Safety net: never touches profiles named in our
    canonical PROFILES list, even if they appear unused right now
    (avoids deleting a profile mid-rollout before assignments are applied).

    Returns: (deleted_role_profiles, deleted_module_profiles).
    """
    canonical_names = {p["name"] for p in PROFILES}
    deleted_role, deleted_module = [], []

    # ─── Role Profiles ───
    all_role_profiles = frappe.get_all(
        "Role Profile", pluck="name", ignore_permissions=True,
    )
    for rp_name in all_role_profiles:
        if rp_name in canonical_names:
            continue  # never delete a canonical CDN profile
        # Any user holding this Role Profile?
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

    # ─── Module Profiles ───
    all_module_profiles = frappe.get_all(
        "Module Profile", pluck="name", ignore_permissions=True,
    )
    for mp_name in all_module_profiles:
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
    """Print current state of all profiles + user assignments. Useful
    after deploy or troubleshooting."""
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

    print("\n=== User Assignments ===\n")
    for user, expected in USER_PROFILE_MAP.items():
        if not frappe.db.exists("User", user):
            print(f"  ✗ {user:35s} (user missing)")
            continue
        actual = frappe.db.get_value("User", user, "role_profile_name")
        match = "✓" if actual == expected else "⚠"
        print(f"  {match} {user:35s} expected={expected!r:30s} actual={actual!r}")
