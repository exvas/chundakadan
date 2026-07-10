import frappe
from frappe import _
from frappe.model.document import Document
from chundakadan.display_tracking.transitions import resolve_transition, LOCATION_DOCTYPE


class DisplayMovement(Document):
    def before_insert(self):
        # Derive from/to state here (NOT validate): Frappe runs _validate_links
        # before run_before_save_methods, so the Dynamic Link companion
        # doctype fields must be populated before that link check.
        self._derive_state()

    def before_submit(self):
        # Re-derive defensively in case a draft was edited before submit.
        self._derive_state()

    def _derive_state(self):
        unit = frappe.get_doc("Display Unit", self.display_unit)
        # snapshot the "from" side from the unit's current cache
        self.from_status = unit.current_status
        self.from_location_type = unit.current_location_type
        self.from_location = unit.current_location
        self.from_location_doctype = LOCATION_DOCTYPE.get(unit.current_location_type)
        if not self.user:
            self.user = frappe.session.user

        t = resolve_transition(self.movement_type, unit.current_status)
        self.to_status = t["to_status"]
        # to_location_type None means "leave the unit's location unchanged"
        if t["to_location_type"] is None:
            self.to_location_type = unit.current_location_type
            if not self.to_location:
                self.to_location = unit.current_location
        elif not self.to_location_type:
            self.to_location_type = t["to_location_type"]
        self.to_location_doctype = LOCATION_DOCTYPE.get(self.to_location_type)

        for field in t["requires"]:
            if not self.get(field):
                frappe.throw(_("'{0}' is required for movement '{1}'.").format(
                    self.meta.get_label(field), self.movement_type))

    def on_submit(self):
        self._write_unit_state()

    def on_cancel(self):
        if "Display Manager" not in frappe.get_roles(frappe.session.user):
            frappe.throw(_("Only a Display Manager may cancel a movement. "
                           "Log a reversing movement instead."))
        self._recompute_unit_from_history()

    # -- helpers ---------------------------------------------------------
    def _write_unit_state(self):
        vals = {
            "current_status": self.to_status,
            "current_location_type": self.to_location_type,
            "current_location": self.to_location,
            "current_location_doctype": LOCATION_DOCTYPE.get(self.to_location_type),
            "current_custodian": self.custodian,
            "current_customer": self.customer,
            "customer_branch": self.customer_branch,
            "contact_person": self.contact_person,
            "expected_return_date": self.expected_return_date,
            "last_movement": self.name,
            "last_movement_on": self.movement_datetime,
        }
        if self.movement_type in ("Install at Customer", "Transfer"):
            vals["delivery_date"] = frappe.utils.getdate(self.movement_datetime)
        frappe.db.set_value("Display Unit", self.display_unit, vals)

    def _recompute_unit_from_history(self):
        prev = frappe.get_all(
            "Display Movement",
            filters={"display_unit": self.display_unit, "docstatus": 1,
                     "name": ["!=", self.name]},
            order_by="movement_datetime desc, creation desc", limit=1, pluck="name")
        if prev:
            frappe.get_doc("Display Movement", prev[0])._write_unit_state()
        else:
            supplier = frappe.db.get_value("Display Unit", self.display_unit, "supplier")
            frappe.db.set_value("Display Unit", self.display_unit, {
                "current_status": "At Supplier", "current_location_type": "Supplier",
                "current_location": supplier, "current_location_doctype": "Supplier",
                "current_custodian": None, "current_customer": None,
                "customer_branch": None, "contact_person": None,
                "expected_return_date": None, "last_movement": None, "last_movement_on": None,
            })
