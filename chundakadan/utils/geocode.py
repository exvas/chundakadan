# Copyright (c) 2026, Chundakadan
# Reverse-geocode (lat, long) -> human-readable address via OpenStreetMap
# Nominatim, then write into a `custom_location` field on the calling
# doctype. Used by both Employee Checkin and Customer Visit Log
# after_insert hooks so HR / Sales can see "where did this happen"
# without copying coordinates into Maps.
#
# Nominatim usage policy: 1 req/sec hard limit + a User-Agent header.
# We enqueue to the long queue so a burst of inserts doesn't serialise
# on the live request.

import frappe


def resolve_for_doc(
    doc,
    lat_field="latitude",
    lon_field="longitude",
    location_field="custom_location",
):
    """Generic after_insert helper. Enqueues a background geocode for
    `doc` and writes the result into `location_field` if the doctype
    has it. Idempotent — skips silently when:
      - no coordinates on the doc
      - the destination field doesn't exist (Custom Field not created)
      - the field is already populated (re-running on save shouldn't
        re-bill Nominatim)

    Caller wires this as a doc_events.after_insert hook with the
    appropriate field names if they differ from the defaults.
    """
    lat = doc.get(lat_field)
    lon = doc.get(lon_field)
    if not (lat and lon):
        return
    # Field-staff checkins carry a tiny non-zero placeholder (1e-6, set in
    # field_sales.create_employee_checkin) so HRMS's "lat/long required"
    # throw doesn't fire. That point is Null Island (0,0) — Nominatim
    # returns {'error': 'Unable to geocode'} and we'd log a bogus
    # "empty display_name" error for every field punch. Skip anything
    # within ~1km of (0,0); every real Chundakadan coordinate is in Kerala
    # (~11,75) and never lands here.
    try:
        if abs(float(lat)) < 0.01 and abs(float(lon)) < 0.01:
            return
    except (TypeError, ValueError):
        return
    if not doc.meta.has_field(location_field):
        return
    if doc.get(location_field):
        return

    frappe.enqueue(
        "chundakadan.utils.geocode._geocode_and_save",
        queue="long",
        timeout=120,
        job_name=f"geocode_{doc.doctype}_{doc.name}",
        doctype=doc.doctype,
        name=doc.name,
        lat=str(lat),
        lon=str(lon),
        location_field=location_field,
    )


def _geocode_and_save(doctype, name, lat, lon, location_field="custom_location"):
    """Background job — runs in the long queue. Calls Nominatim's reverse
    geocoder, takes the display_name (full comma-separated address),
    trims to 250 chars to fit Small Text, and writes via db.set_value
    so we bypass any submit-state restrictions on the parent doctype.

    Returns the resolved address (or None if anything failed). Logs
    non-200 responses + exceptions so silent failures are visible in
    the Error Log.
    """
    import requests
    import time

    try:
        res = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": lat,
                "lon": lon,
                "format": "json",
                "zoom": 18,
                "addressdetails": 1,
            },
            headers={
                "User-Agent": (
                    "chundakadan-erp/1.0 "
                    "(contact: sammish.thundiyil@gmail.com)"
                ),
            },
            timeout=15,
        )

        # 429 = rate-limit. Retry once after a short pause; if still
        # rate-limited, log and bail (caller can re-queue later).
        if res.status_code == 429:
            time.sleep(2)
            res = requests.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": lat, "lon": lon, "format": "json",
                    "zoom": 18, "addressdetails": 1,
                },
                headers={
                    "User-Agent": (
                        "chundakadan-erp/1.0 "
                        "(contact: sammish.thundiyil@gmail.com)"
                    ),
                },
                timeout=15,
            )

        if res.status_code != 200:
            # Log so silent 429/403/5xx are visible. Truncate body —
            # Nominatim returns long HTML on errors.
            frappe.log_error(
                f"chundakadan.utils.geocode: HTTP {res.status_code}",
                f"doctype={doctype} name={name} lat={lat} lon={lon}\n"
                f"body={res.text[:400]}",
            )
            return None

        data = res.json()
        # Nominatim signals an un-geocodable point with {'error': ...}
        # (e.g. ocean / Null Island placeholder coords) rather than an
        # address. That's not a system fault — there is simply no address
        # there — so return quietly instead of logging an error per row.
        if isinstance(data, dict) and data.get("error"):
            return None
        address = (data.get("display_name") or "").strip()
        if not address:
            return None

        if len(address) > 250:
            address = address[:247] + "…"
        frappe.db.set_value(
            doctype, name, location_field, address,
            update_modified=False,
        )
        frappe.db.commit()
        return address
    except Exception:
        frappe.log_error(
            f"chundakadan.utils.geocode._geocode_and_save:{doctype}",
            frappe.get_traceback(),
        )
        return None


def backfill_synchronously(
    doctype,
    lat_field="latitude",
    lon_field="longitude",
    location_field="custom_location",
    delay=1.2,
    limit=5000,
):
    """Walk every unresolved row of `doctype` IN ORDER and call
    _geocode_and_save synchronously with a delay between requests.

    Stays strictly under Nominatim's 1 req/sec policy by default
    (delay=1.2). Use this for the initial backfill instead of the
    enqueue-everything-at-once approach, which trips the rate limit
    when multiple workers run jobs in parallel.

    Prints progress every 25 rows. Safe to interrupt + resume (the
    next call skips rows that already have a location).

    Usage:
        from chundakadan.utils.geocode import backfill_synchronously
        backfill_synchronously("Customer Visit Log")
    """
    import time

    rows = frappe.db.sql(
        f"""
        SELECT name, `{lat_field}` as lat, `{lon_field}` as lon
        FROM `tab{doctype}`
        WHERE `{lat_field}` IS NOT NULL AND `{lat_field}` != 0
          AND (`{location_field}` IS NULL OR `{location_field}` = '')
        LIMIT {int(limit)}
        """,
        as_dict=True,
    )
    print(f"Processing {len(rows)} unresolved rows of '{doctype}'…")

    ok = fail = 0
    for i, r in enumerate(rows, start=1):
        result = _geocode_and_save(
            doctype, r["name"], str(r["lat"]), str(r["lon"]),
            location_field=location_field,
        )
        if result:
            ok += 1
        else:
            fail += 1
        if i % 25 == 0:
            print(f"  {i}/{len(rows)}  ok={ok}  fail={fail}")
        time.sleep(delay)

    print(f"Done. ok={ok} fail={fail} total={len(rows)}")
    return {"ok": ok, "fail": fail, "total": len(rows)}


def backfill_locations(
    doctype,
    lat_field="latitude",
    lon_field="longitude",
    location_field="custom_location",
    limit=500,
):
    """Enqueue Nominatim reverse-geocoding for every existing row of
    `doctype` that has lat/long but no resolved location yet. Skips
    rows where the field is already populated (re-runnable / safe to
    call repeatedly).

    Usage:
        from chundakadan.utils.geocode import backfill_locations
        backfill_locations("Customer Visit Log")
        backfill_locations("Employee Checkin",
                           lat_field="custom_latitude",
                           lon_field="custom_longitude")

    Returns the count of jobs enqueued.
    """
    rows = frappe.get_all(
        doctype,
        filters={
            lat_field: ["!=", 0],
            lon_field: ["!=", 0],
            location_field: ["in", [None, ""]],
        },
        fields=["name", lat_field, lon_field],
        limit=limit,
        ignore_permissions=True,
    )
    queued = 0
    for r in rows:
        lat = r.get(lat_field)
        lon = r.get(lon_field)
        if not (lat and lon):
            continue
        frappe.enqueue(
            "chundakadan.utils.geocode._geocode_and_save",
            queue="long",
            timeout=120,
            job_name=f"geocode_backfill_{doctype}_{r['name']}",
            doctype=doctype,
            name=r["name"],
            lat=str(lat),
            lon=str(lon),
            location_field=location_field,
        )
        queued += 1
    return queued
