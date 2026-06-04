# Copyright (c) 2026, Chundakadan
# Doc-event hooks for Customer Visit Log.

from chundakadan.utils.geocode import resolve_for_doc


def resolve_location(doc, method=None):
    """Reverse-geocode the visit's lat/long → custom_location.
    Customer Visit Log uses the same field names as Employee Checkin
    (latitude / longitude), so the shared util works without any
    overrides. Wired as after_insert in chundakadan/hooks.py.
    """
    resolve_for_doc(doc)
