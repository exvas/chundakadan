# Auto-generated Holiday Lists for chundakadan (Kerala, India).
#
# Strategy: each year we generate a Holiday List named `CDN-<YEAR>` with:
#   - All Sundays as weekly-off
#   - India national holidays (fixed dates + pre-calculated movable
#     dates for the next 5 years)
#   - Kerala state holidays (Onam, Vishu, Mahavir Jayanti, etc.)
#
# Wired into:
#   - before_migrate hook (ensures current year + next year exist)
#   - scheduler_events cron (Jan 1 — generates the new year, sets as
#     Company default, propagates to Employees that don't yet have one)
#
# To extend beyond 2030: append entries to `_HOLIDAYS_BY_YEAR` below.
# Fixed-date holidays (Republic Day, Independence Day, Christmas, etc.)
# are auto-handled — no manual entry needed.

import frappe
from datetime import date, timedelta


COMPANY = "Chundakadan Agencies"


# ─────────────────────────────────────────────────────────────────────
# HOLIDAY DATA
# ─────────────────────────────────────────────────────────────────────

# Always-on fixed-date holidays (any year)
_FIXED_HOLIDAYS = [
    # (month, day, description)
    (1, 1,  "New Year's Day"),
    (1, 26, "Republic Day"),
    (5, 1,  "May Day / Labour Day"),
    (8, 15, "Independence Day"),
    (10, 2, "Gandhi Jayanti"),
    (12, 25, "Christmas"),
]


# Variable-date holidays — pre-calculated per year (Kerala calendar).
# Sources: official Kerala govt holiday gazette + Indian astronomical
# calendar for lunar dates. Extend each January when new govt list drops.
_HOLIDAYS_BY_YEAR = {
    2026: [
        (date(2026, 1, 14),  "Pongal / Makar Sankranti"),
        (date(2026, 3, 4),   "Maha Shivaratri"),
        (date(2026, 3, 21),  "Holi"),
        (date(2026, 4, 3),   "Good Friday"),
        (date(2026, 4, 14),  "Vishu"),
        (date(2026, 5, 1),   "Labour Day"),  # already fixed but Kerala emphasises
        (date(2026, 5, 21),  "Eid al-Fitr"),
        (date(2026, 7, 28),  "Bakrid / Eid al-Adha"),
        (date(2026, 8, 27),  "Onam (Day 1 — Uthradam)"),
        (date(2026, 8, 28),  "Thiruvonam"),
        (date(2026, 8, 29),  "Onam (Day 3)"),
        (date(2026, 10, 20), "Diwali"),
        (date(2026, 11, 24), "Guru Nanak Jayanti"),
    ],
    2027: [
        (date(2027, 1, 14),  "Pongal / Makar Sankranti"),
        (date(2027, 2, 21),  "Maha Shivaratri"),
        (date(2027, 3, 22),  "Holi"),
        (date(2027, 3, 26),  "Good Friday"),
        (date(2027, 4, 14),  "Vishu"),
        (date(2027, 5, 10),  "Eid al-Fitr"),
        (date(2027, 7, 18),  "Bakrid / Eid al-Adha"),
        (date(2027, 9, 14),  "Onam (Day 1 — Uthradam)"),
        (date(2027, 9, 15),  "Thiruvonam"),
        (date(2027, 9, 16),  "Onam (Day 3)"),
        (date(2027, 11, 8),  "Diwali"),
        (date(2027, 11, 13), "Guru Nanak Jayanti"),
    ],
    2028: [
        (date(2028, 1, 14),  "Pongal / Makar Sankranti"),
        (date(2028, 2, 10),  "Maha Shivaratri"),
        (date(2028, 3, 11),  "Holi"),
        (date(2028, 4, 14),  "Vishu"),
        (date(2028, 4, 14),  "Good Friday"),
        (date(2028, 4, 27),  "Eid al-Fitr"),
        (date(2028, 7, 6),   "Bakrid / Eid al-Adha"),
        (date(2028, 9, 3),   "Onam (Day 1)"),
        (date(2028, 9, 4),   "Thiruvonam"),
        (date(2028, 10, 26), "Diwali"),
    ],
    2029: [
        (date(2029, 1, 14),  "Pongal / Makar Sankranti"),
        (date(2029, 2, 13),  "Maha Shivaratri"),
        (date(2029, 3, 1),   "Holi"),
        (date(2029, 3, 30),  "Good Friday"),
        (date(2029, 4, 14),  "Eid al-Fitr"),
        (date(2029, 4, 14),  "Vishu"),
        (date(2029, 6, 25),  "Bakrid / Eid al-Adha"),
        (date(2029, 9, 21),  "Onam (Day 1)"),
        (date(2029, 9, 22),  "Thiruvonam"),
        (date(2029, 11, 14), "Diwali"),
    ],
    2030: [
        (date(2030, 1, 14),  "Pongal / Makar Sankranti"),
        (date(2030, 3, 2),   "Maha Shivaratri"),
        (date(2030, 3, 20),  "Holi"),
        (date(2030, 4, 4),   "Eid al-Fitr"),
        (date(2030, 4, 14),  "Vishu"),
        (date(2030, 4, 19),  "Good Friday"),
        (date(2030, 6, 14),  "Bakrid / Eid al-Adha"),
        (date(2030, 9, 11),  "Onam (Day 1)"),
        (date(2030, 9, 12),  "Thiruvonam"),
        (date(2030, 11, 4),  "Diwali"),
    ],
}


# ─────────────────────────────────────────────────────────────────────
# CORE GENERATOR
# ─────────────────────────────────────────────────────────────────────

def _all_sundays(year):
    """Generate every Sunday in the given year."""
    d = date(year, 1, 1)
    # Move to the first Sunday
    d += timedelta(days=(6 - d.weekday()) % 7)
    while d.year == year:
        yield d
        d += timedelta(days=7)


def _holidays_for_year(year):
    """Return list of (date, description, weekly_off) tuples."""
    rows = []

    # Weekly off (Sundays)
    for sun in _all_sundays(year):
        rows.append((sun, "Sunday", 1))

    # Fixed-date holidays
    for month, day, desc in _FIXED_HOLIDAYS:
        try:
            d = date(year, month, day)
            rows.append((d, desc, 0))
        except ValueError:
            # e.g., Feb 29 on non-leap year — skip silently
            pass

    # Variable-date holidays from the year-specific table
    for d, desc in _HOLIDAYS_BY_YEAR.get(year, []):
        rows.append((d, desc, 0))

    # Deduplicate by date — keep the more specific description
    by_date = {}
    for d, desc, weekly in rows:
        if d in by_date:
            # Prefer specific holiday names over "Sunday"
            existing = by_date[d]
            if existing[1] == "Sunday" and desc != "Sunday":
                by_date[d] = (d, desc, weekly)
        else:
            by_date[d] = (d, desc, weekly)

    return sorted(by_date.values())


def generate_holiday_list(year, force=False):
    """Create (or replace if force=True) a Holiday List for the given
    year. Returns the doctype name.

    Idempotent: skips if a list for the year already exists, unless
    force=True.
    """
    name = f"CDN-{year}"

    if frappe.db.exists("Holiday List", name):
        if not force:
            print(f"  · {name} already exists — skip (use force=True to regenerate)")
            return name
        # Force regenerate — delete the existing one (if no Allocations)
        try:
            frappe.delete_doc("Holiday List", name,
                              ignore_permissions=True, force=1)
            print(f"  - deleted existing {name} to regenerate")
        except Exception as e:
            print(f"  ✗ could not delete {name}: {e}")
            return name

    rows = _holidays_for_year(year)

    doc = frappe.get_doc({
        "doctype": "Holiday List",
        "holiday_list_name": name,
        "from_date": str(date(year, 1, 1)),
        "to_date":   str(date(year, 12, 31)),
        "weekly_off": "Sunday",
        "color": "#b8860b",  # chundakadan gold
        "holidays": [
            {
                "doctype": "Holiday",
                "holiday_date": str(d),
                "description": desc,
                "weekly_off": weekly,
            }
            for d, desc, weekly in rows
        ],
    })
    doc.flags.ignore_permissions = True
    doc.insert()

    n_weekly = sum(1 for _, _, w in rows if w)
    n_holidays = len(rows) - n_weekly
    print(f"  ✓ Created {name}: {n_weekly} Sundays + {n_holidays} holidays")
    return name


# ─────────────────────────────────────────────────────────────────────
# AUTO-INSTALL HOOKS
# ─────────────────────────────────────────────────────────────────────

def ensure_current_and_next_year(*args, **kwargs):
    """Wired as before_migrate. Ensures Holiday Lists exist for both
    the current calendar year AND the next year (so HR can apply leave
    + payroll without waiting for the Jan 1 cron).

    Also sets the current year's list as Company default if Company
    doesn't already have one.
    """
    from datetime import date
    today = date.today()
    years = [today.year, today.year + 1]

    print(f"chundakadan.seed.holiday_list: ensuring lists for {years}")
    last_created = None
    for year in years:
        # Only generate if we have data for it (or if it's a year we
        # can compute fixed-date holidays for)
        if year not in _HOLIDAYS_BY_YEAR and year > 2030:
            print(f"  ⚠ year {year}: no variable-date holidays defined — "
                  f"will only have Sundays + fixed-date holidays. "
                  f"Update _HOLIDAYS_BY_YEAR in seed/holiday_list.py.")
        try:
            last_created = generate_holiday_list(year)
        except Exception as e:
            print(f"  ✗ year {year}: {e}")

    # Set as Company default if not already set
    if frappe.db.exists("Company", COMPANY):
        current = frappe.db.get_value("Company", COMPANY,
                                      "default_holiday_list")
        current_year_list = f"CDN-{today.year}"
        if not current and frappe.db.exists("Holiday List", current_year_list):
            frappe.db.set_value("Company", COMPANY,
                                "default_holiday_list", current_year_list)
            print(f"  ✓ Set Company default = {current_year_list}")


def annual_holiday_refresh():
    """Wired as a yearly Jan 1 cron. Generates the NEW current year's
    Holiday List + updates Company default + propagates to Employees
    that still hold the previous year's list.

    Standard scheduler config (chundakadan/hooks.py):
        scheduler_events = {
            "cron": {
                "0 0 1 1 *":
                    ["chundakadan.seed.holiday_list.annual_holiday_refresh"],
            }
        }
    """
    from datetime import date
    today = date.today()
    current_year = today.year
    current_list = f"CDN-{current_year}"

    print(f"chundakadan.seed.holiday_list: annual refresh for {current_year}")

    # 1. Create this year's list if missing
    if not frappe.db.exists("Holiday List", current_list):
        generate_holiday_list(current_year)

    # 2. Pre-create next year's list too (so leave allocation cycles
    #    don't break on Dec 31)
    next_year = current_year + 1
    next_list = f"CDN-{next_year}"
    if not frappe.db.exists("Holiday List", next_list):
        generate_holiday_list(next_year)

    # 3. Update Company default if it's still pointing at a past list
    company_default = frappe.db.get_value("Company", COMPANY,
                                           "default_holiday_list")
    if company_default != current_list:
        frappe.db.set_value("Company", COMPANY,
                            "default_holiday_list", current_list)
        print(f"  ✓ Company default updated: {company_default} → {current_list}")

    # 4. Update Employees still on the previous year's list
    prev_list = f"CDN-{current_year - 1}"
    if frappe.db.exists("Holiday List", prev_list):
        updated = frappe.db.sql("""
            UPDATE `tabEmployee`
            SET holiday_list = %s
            WHERE status = 'Active' AND holiday_list = %s
        """, (current_list, prev_list))
        n = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
        if n:
            print(f"  ✓ Migrated {n} Employees: {prev_list} → {current_list}")

    frappe.db.commit()
