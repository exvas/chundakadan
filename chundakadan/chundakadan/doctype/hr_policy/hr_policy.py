# Copyright (c) 2026, Chundakadan
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class HRPolicy(Document):
    """Singleton — only one record. HR uploads the CDN POLICY PDF and/or
    fills the rich-text version. Every save bumps `version` and stamps
    last_updated_by/_on. The on_update hook in chundakadan/hooks.py
    triggers a push notification to all Active employees (when
    notify_on_update is checked).
    """

    def before_save(self):
        if not (self.policy_pdf or (self.policy_html or "").strip()):
            frappe.throw(
                _("Provide a Policy PDF or a Rich Text policy (or both) before saving.")
            )

        # Auto-increment version + stamp updater
        self.version = (self.version or 0) + 1
        self.last_updated_by = frappe.session.user
        self.last_updated_on = frappe.utils.now()
