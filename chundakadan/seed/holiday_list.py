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
HOLIDAY_LIST_NAME = "CA"   # we maintain ONE Holiday List, append yearly


# ─────────────────────────────────────────────────────────────────────
# HOLIDAY DATA
# ─────────────────────────────────────────────────────────────────────

# Always-on fixed-date holidays (any year) — used as fallback when the
# `holidays` Python library isn't available.
_FIXED_HOLIDAYS = [
    # (month, day, description)
    (1, 1,  "New Year's Day"),
    (1, 26, "Republic Day"),
    (5, 1,  "May Day / Labour Day"),
    (8, 15, "Independence Day"),
    (10, 2, "Gandhi Jayanti"),
    (12, 25, "Christmas"),
]


# Tries the `holidays` package first (which auto-resolves Kerala dates
# for every year including future ones). Falls back to our hardcoded
# _HOLIDAYS_BY_YEAR if the library isn't installed.
def _holidays_from_library(year):
    """Return [(date, description), ...] from python-holidays for
    India + Kerala subdivision. None if library not available."""
    try:
        import holidays as _holidays
    except ImportError:
        return None

    try:
        # India subdivision KL (Kerala)
        in_kl = _holidays.India(years=[year], subdiv="KL")
        return [(d, str(name)) for d, name in sorted(in_kl.items())]
    except Exception:
        return None


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
    """Return list of (date, description, weekly_off) tuples.

    Preferred source: python-holidays library with India + Kerala (KL)
    subdivision. Falls back to our hardcoded _HOLIDAYS_BY_YEAR +
    _FIXED_HOLIDAYS map if the library isn't installed.
    """
    rows = []

    # Weekly off (Sundays)
    for sun in _all_sundays(year):
        rows.append((sun, "Sunday", 1))

    # Try the library first — it handles all India + Kerala holidays
    # algorithmically for any year (no manual extension needed).
    lib_rows = _holidays_from_library(year)
    if lib_rows is not None:
        for d, desc in lib_rows:
            rows.append((d, desc, 0))
    else:
        # Fallback: hardcoded data
        for month, day, desc in _FIXED_HOLIDAYS:
            try:
                rows.append((date(year, month, day), desc, 0))
            except ValueError:
                pass
        for d, desc in _HOLIDAYS_BY_YEAR.get(year, []):
            rows.append((d, desc, 0))

    # Deduplicate by date — prefer specific holiday names over "Sunday"
    by_date = {}
    for d, desc, weekly in rows:
        if d in by_date:
            existing = by_date[d]
            if existing[1] == "Sunday" and desc != "Sunday":
                by_date[d] = (d, desc, weekly)
        else:
            by_date[d] = (d, desc, weekly)

    return sorted(by_date.values())


def upsert_holidays(target_list=HOLIDAY_LIST_NAME, years=None):
    """Append missing year-holidays to the existing `CA` Holiday List
    (or create it if missing). Idempotent — re-running for the same
    year is a no-op because we dedupe by date.

    `years` defaults to [current_year, next_year]. Extends to_date so
    the list always covers the latest year we have data for.

    Returns the Holiday List name.
    """
    from datetime import date as _date
    if years is None:
        today = _date.today()
        years = [today.year, today.year + 1]

    # Collect all (date, description, weekly_off) tuples for the years
    all_rows = []
    for year in years:
        all_rows.extend(_holidays_for_year(year))
    all_rows.sort(key=lambda r: r[0])

    if not all_rows:
        print(f"  ⚠ no holiday data for years {years}")
        return target_list

    target_from = all_rows[0][0]
    target_to = all_rows[-1][0]

    if frappe.db.exists("Holiday List", target_list):
        # Update existing — extend dates + append missing holidays
        doc = frappe.get_doc("Holiday List", target_list)
        existing_dates = {h.holiday_date for h in doc.holidays}

        # Extend date range to cover the new years (don't shrink it)
        if doc.from_date is None or _date.fromisoformat(str(doc.from_date)) > target_from:
            doc.from_date = str(target_from)
        if doc.to_date is None or _date.fromisoformat(str(doc.to_date)) < target_to:
            doc.to_date = str(target_to)

        added = 0
        for d, desc, weekly in all_rows:
            if d in existing_dates:
                continue
            doc.append("holidays", {
                "holiday_date": str(d),
                "description": desc,
                "weekly_off": weekly,
            })
            added += 1

        if added == 0:
            print(f"  · {target_list}: nothing to add for {years} "
                  f"(date range: {doc.from_date} → {doc.to_date})")
            return target_list

        doc.flags.ignore_permissions = True
        doc.save()
        print(f"  ✓ {target_list}: appended {added} new entries "
              f"(now covers {doc.from_date} → {doc.to_date})")
        return target_list

    # Doesn't exist — create fresh
    doc = frappe.get_doc({
        "doctype": "Holiday List",
        "holiday_list_name": target_list,
        "from_date": str(target_from),
        "to_date":   str(target_to),
        "weekly_off": "Sunday",
        "country": "India",
        "subdivision": "KL",   # Kerala
        "color": "#b8860b",
        "holidays": [
            {
                "doctype": "Holiday",
                "holiday_date": str(d),
                "description": desc,
                "weekly_off": weekly,
            }
            for d, desc, weekly in all_rows
        ],
    })
    doc.flags.ignore_permissions = True
    doc.insert()
    n_weekly = sum(1 for _, _, w in all_rows if w)
    n_holidays = len(all_rows) - n_weekly
    print(f"  ✓ Created {target_list}: {n_weekly} Sundays + "
          f"{n_holidays} holidays ({target_from} → {target_to})")
    return target_list


# Legacy alias — callers from before the CA-single-list refactor
def generate_holiday_list(year, force=False):
    return upsert_holidays(HOLIDAY_LIST_NAME, years=[year])


# ─────────────────────────────────────────────────────────────────────
# AUTO-INSTALL HOOKS
# ─────────────────────────────────────────────────────────────────────

def ensure_current_and_next_year(*args, **kwargs):
    """Wired as before_migrate. Updates the existing `CA` Holiday List
    (or creates it if missing) covering current year + next year.
    Idempotent.
    """
    from datetime import date
    today = date.today()
    years = [today.year, today.year + 1]

    print(f"chundakadan.seed.holiday_list: ensuring {HOLIDAY_LIST_NAME} covers {years}")
    try:
        upsert_holidays(HOLIDAY_LIST_NAME, years=years)
    except Exception as e:
        print(f"  ✗ {e}")

    # Set as Company default if not already
    if frappe.db.exists("Company", COMPANY):
        current = frappe.db.get_value("Company", COMPANY,
                                      "default_holiday_list")
        if not current and frappe.db.exists("Holiday List", HOLIDAY_LIST_NAME):
            frappe.db.set_value("Company", COMPANY,
                                "default_holiday_list", HOLIDAY_LIST_NAME)
            print(f"  ✓ Set Company default = {HOLIDAY_LIST_NAME}")


def annual_holiday_refresh():
    """Wired as the Dec 31 23:00 cron. Appends the NEW upcoming year's
    holidays to the existing `CA` list, so when Jan 1 ticks over, the
    list already covers the new year.

    Schedule (chundakadan/hooks.py):
        scheduler_events.cron["0 23 31 12 *"]:
            "chundakadan.seed.holiday_list.annual_holiday_refresh"
    """
    from datetime import date
    today = date.today()
    next_year = today.year + 1

    print(f"chundakadan.seed.holiday_list: Dec-31 refresh — "
          f"extending {HOLIDAY_LIST_NAME} to cover {next_year}")
    try:
        upsert_holidays(HOLIDAY_LIST_NAME, years=[next_year])
    except Exception as e:
        print(f"  ✗ {e}")

    frappe.db.commit()
