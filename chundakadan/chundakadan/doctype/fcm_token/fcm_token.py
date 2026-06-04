# Copyright (c) 2026, Chundakadan
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FCMToken(Document):
    """Stores Firebase Cloud Messaging registration tokens per user/device.
    Multiple rows per user allowed — one per device. The mobile app calls
    field_sales.Api.auth.save_fcm_token after login; if the same token
    already exists for the user, we update last_seen instead of inserting
    a duplicate (handled in the API layer, not here).
    """

    def before_insert(self):
        if not self.last_seen:
            self.last_seen = frappe.utils.now()
