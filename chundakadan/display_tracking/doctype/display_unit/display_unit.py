import frappe
from frappe.model.document import Document
from chundakadan.display_tracking.transitions import LOCATION_DOCTYPE


class DisplayUnit(Document):
    def before_insert(self):
        if not self.current_status:
            self.current_status = "At Supplier"
            self.current_location_type = "Supplier"
            self.current_location = self.supplier
        self.current_location_doctype = LOCATION_DOCTYPE.get(self.current_location_type)

    def after_insert(self):
        if self.barcode != self.name:
            frappe.db.set_value("Display Unit", self.name, "barcode", self.name,
                                update_modified=False)
            self.barcode = self.name
