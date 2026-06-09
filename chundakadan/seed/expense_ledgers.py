"""Expense Ledgers + Expense Claim Types (Chundakadan, 2026-06-09)

Source: Chundakadan's "Expense List" Word doc (2026-06-09).

Creates 11 group accounts under "5200 Indirect Expenses" mirroring the
12 doc sections (section 1 = Purchase / COGS, already in CoA, skipped).
Each group holds the leaf ledgers listed in the doc. Then creates the
employee-reimbursable Expense Claim Types with per-company default
account links.

Skipped on purpose (already in CoA + wired to Payroll postings):
  - Salaries & Allowances        (use 5301 Salary)
  - PF Employer Contributions    (Salary Component already maps)
  - ESI Employer Contributions   (Salary Component already maps)

Idempotent — safe to re-run. Run via:
  bench --site <site> execute chundakadan.seed.expense_ledgers.seed_expense_ledgers
"""
import frappe


# -- 11 group accounts -------------------------------------------------
# Codes 5230-5290 + 5350-5380 (skip 5300-5309 which Payroll Expenses owns).
EXPENSE_GROUPS = [
    ("5230", "Logistics and Distribution Expenses"),
    ("5240", "Warehouse and Storage Expenses"),
    ("5250", "Employee-Related Expenses"),
    ("5260", "Sales and Marketing Expenses"),
    ("5270", "Office and Administrative Expenses"),
    ("5280", "Vehicle Expenses"),
    ("5290", "Finance and Banking Expenses"),
    ("5350", "Professional and Compliance Expenses"),
    ("5360", "Information Technology Expenses"),
    ("5370", "Repairs and Maintenance"),
    ("5380", "Miscellaneous Business Expenses"),
]

PARENT_INDIRECT = "5200 - Indirect Expenses"   # suffix " - <abbr>" added per company


# -- Leaf ledgers per group --------------------------------------------
# Names normalized to Title Case; stripped of trailing "expense(s)" noise
# only where the section already names the bucket.
LEAVES = {
    "5230": [
        "Transportation Charges",
        "Freight Outward",
        "Courier and Parcel Charges",
        "Loading and Unloading Charges",
        "Packaging Materials",
    ],
    "5240": [
        "Warehouse Rent",
        "Godown Maintenance",
        "Material Handling Equipment Maintenance",
        "Insurance on Stock",
    ],
    "5250": [
        # Skip: Salaries & Allowances, PF Employer, ESI Employer
        # (mapped to 5301 / Salary Components).
        "Incentive for Sales Staff",
        "Incentive for Other Staff",
        "Festival Allowance",
        "EPF Administration Charge",
        "Staff Welfare Expenses",
        "Training Expenses",
        "ID Card Printing Expense",
        "Uniform Expense",
    ],
    "5260": [
        "Discounts Allowed",
        "Advertisement Expenses",
        "Marketing Expenses",
        "Exhibition Expense",
        "Product Catalog Printing",
        "Sample Materials",
    ],
    "5270": [
        "Office Rent",
        "Electricity Charges",
        "Internet and Telephone Expenses",
        "Mobile Recharge",
        "Stationery Expense",
        "Printing Expense",
        "Postage Expense",
        "Courier Expenses",
        "Meeting Expenses",
        "Refreshments Expenses",
        "Housekeeping Expenses",
    ],
    "5280": [
        "Fuel",
        "Vehicle Maintenance",
        "Vehicle Insurance",
        "Driver Salary",
        "Parking Charges",
        "Road Tax",
    ],
    "5290": [
        "Bank Charges",
        "Bank Interest",
    ],
    "5350": [
        "Audit Fees",
        "Accounting Fees",
        "Legal Fees",
        "GST Consultant Fees",
        "ROC Filing Fees",
    ],
    "5360": [
        "ERP Software Expenses",
        "Accounting Software Subscriptions",
        "Website Maintenance",
        "Cloud Storage",
        "Computer Maintenance",
        "Printer Maintenance",
    ],
    "5370": [
        "Office Repairs",
        "Warehouse Repairs",
        "Furniture Maintenance",
        "Electrical Maintenance",
        "Air Condition Maintenance",
    ],
    "5380": [
        "Business Licenses and Permits",
        "Insurance Premiums",
        "Bad Debts Written Off",
        "Donations and Charity Expense",
        "Miscellaneous Expenses",
        "Management Travelling Expense",
    ],
}


# -- Expense Claim Types -----------------------------------------------
# Each entry: (claim_type_name, leaf_account_name)
# leaf_account_name resolves to "<name> - <abbr>" per company.
# Existing types (Calls / Food / Medical / Travel / Others / Travel Allowance)
# also get refreshed account links here.
EXPENSE_CLAIM_TYPES = [
    # name,                       leaf account (or "REUSE:<full account name w/o abbr>")
    ("Fuel",                      "Fuel"),
    ("Mobile Recharge",           "Mobile Recharge"),
    ("Travelling Expense",        "REUSE:5216 - Travel Expenses"),
    ("Refreshments",              "Refreshments Expenses"),
    ("Meeting Expenses",          "Meeting Expenses"),
    ("Courier",                   "Courier Expenses"),
    ("Stationery",                "REUSE:5211 - Print and Stationery"),
    ("ID Card Printing",          "ID Card Printing Expense"),
    ("Uniform",                   "Uniform Expense"),
    ("Training",                  "Training Expenses"),
    ("Sample Materials",          "Sample Materials"),
    ("Vehicle Maintenance",       "Vehicle Maintenance"),
    # Refresh existing types' account mappings:
    ("Calls",                     "REUSE:5215 - Telephone Expenses"),
    ("Travel",                    "REUSE:5216 - Travel Expenses"),
    ("Others",                    "REUSE:5221 - Miscellaneous Expenses"),
    ("Travel Allowance",          "REUSE:5305 - Travel Allowance"),
]


# -- Implementation ----------------------------------------------------

def _account_name(leaf_or_group: str, abbr: str) -> str:
    """Compose the full Account doc-name: '<leaf> - <abbr>'."""
    return f"{leaf_or_group} - {abbr}"


def _ensure_group(code: str, leaf: str, abbr: str, parent: str,
                  company: str) -> str:
    """Create a group account if missing. Returns the full account name."""
    full = f"{code} - {leaf} - {abbr}"
    if frappe.db.exists("Account", full):
        return full
    doc = frappe.get_doc({
        "doctype": "Account",
        "account_name": f"{code} - {leaf}",
        "parent_account": parent,
        "is_group": 1,
        "root_type": "Expense",
        "report_type": "Profit and Loss",
        "company": company,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_leaf(leaf_name: str, parent: str, abbr: str,
                 company: str) -> str:
    """Create a non-group expense account under `parent`. Idempotent."""
    full = f"{leaf_name} - {abbr}"
    if frappe.db.exists("Account", full):
        return full
    doc = frappe.get_doc({
        "doctype": "Account",
        "account_name": leaf_name,
        "parent_account": parent,
        "is_group": 0,
        "root_type": "Expense",
        "report_type": "Profit and Loss",
        "company": company,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _resolve_claim_account(spec: str, abbr: str) -> str | None:
    """Resolve an EXPENSE_CLAIM_TYPES account spec to a real account name.

    Spec forms:
      'Plain Name'                 -> '<Plain Name> - <abbr>'
      'REUSE:5215 - Telephone ...' -> '5215 - Telephone ... - <abbr>'
    """
    if spec.startswith("REUSE:"):
        full = f"{spec[len('REUSE:'):]} - {abbr}"
    else:
        full = f"{spec} - {abbr}"
    return full if frappe.db.exists("Account", full) else None


def seed_expense_ledgers():
    """Idempotent: creates 11 group accounts + ~60 leaf ledgers per
    company + 16 Expense Claim Types with per-company links."""
    companies = frappe.get_all("Company", fields=["name", "abbr"])
    print(f"\n=== Seeding expense ledgers for {len(companies)} companies ===")

    created_groups = 0
    created_leaves = 0
    leaf_by_company = {}  # company -> {leaf_name -> full_account_name}

    for co in companies:
        abbr = co["abbr"]
        company = co["name"]
        leaf_by_company[company] = {}
        print(f"\n--- {company} ({abbr}) ---")
        parent_indirect = _account_name(PARENT_INDIRECT, abbr)
        if not frappe.db.exists("Account", parent_indirect):
            print(f"  ! Missing parent '{parent_indirect}' — skipping company")
            continue

        for code, group_name in EXPENSE_GROUPS:
            try:
                group_full = _ensure_group(code, group_name, abbr,
                                           parent_indirect, company)
                created_groups += 1
                for leaf_name in LEAVES.get(code, []):
                    try:
                        full = _ensure_leaf(leaf_name, group_full, abbr,
                                            company)
                        leaf_by_company[company][leaf_name] = full
                        created_leaves += 1
                    except Exception as e:
                        print(f"  ✗ Leaf {leaf_name}: {e}")
            except Exception as e:
                print(f"  ✗ Group {code} {group_name}: {e}")

        co_leaves = len(leaf_by_company[company])
        print(f"  ✓ {co_leaves} leaf ledgers present under indirect")

    frappe.db.commit()
    print(f"\n  Group ensures: {created_groups}")
    print(f"  Leaf ensures:  {created_leaves}")

    # ---- Expense Claim Types ----
    print("\n=== Expense Claim Types ===")
    for ct_name, account_spec in EXPENSE_CLAIM_TYPES:
        # Create the Expense Claim Type if missing
        if not frappe.db.exists("Expense Claim Type", ct_name):
            ct = frappe.get_doc({
                "doctype": "Expense Claim Type",
                "expense_type": ct_name,
            })
            ct.insert(ignore_permissions=True)
            action = "created"
        else:
            ct = frappe.get_doc("Expense Claim Type", ct_name)
            action = "updated"

        # Wipe + repopulate the per-company account table so we always
        # reflect current ledger names
        ct.set("accounts", [])
        added = []
        for co in companies:
            abbr = co["abbr"]
            company = co["name"]
            account = _resolve_claim_account(account_spec, abbr)
            if account:
                ct.append("accounts", {
                    "company": company,
                    "default_account": account,
                })
                added.append(f"{abbr}->{account.split(' - ')[0]}")
        ct.save(ignore_permissions=True)
        print(f"  ✓ {ct_name:25s} {action:7s} {' | '.join(added)}")

    frappe.db.commit()
    print("\n✓ seed_expense_ledgers complete\n")
