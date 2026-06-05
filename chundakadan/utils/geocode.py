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
    """
    import requests

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
        if res.status_code != 200:
            return
        data = res.json()
        address = (data.get("display_name") or "").strip()
        if not address:
            return
        if len(address) > 250:
            address = address[:247] + "…"
        frappe.db.set_value(
            doctype, name, location_field, address,
            update_modified=False,
        )
        frappe.db.commit()
    except Exception:
        frappe.log_error(
            f"chundakadan.utils.geocode._geocode_and_save:{doctype}",
            frappe.get_traceback(),
        )


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
