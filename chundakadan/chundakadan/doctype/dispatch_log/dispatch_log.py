# Copyright (c) 2026, Chundakadan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cstr, getdate, now_datetime

from chundakadan.dispatch import constants as C

# current status -> statuses it may move to
ALLOWED_TRANSITIONS = {
	C.PENDING: {C.PENDING, C.DISPATCHED, C.PICKUP},
	C.DISPATCHED: {C.DISPATCHED, C.DELIVERED, C.NOT_DELIVERED},
	C.NOT_DELIVERED: {C.NOT_DELIVERED, C.DELIVERED},
	C.PICKUP: {C.PICKUP},
	C.DELIVERED: {C.DELIVERED},
}


class DispatchLog(Document):
	def validate(self):
		previous = self.get_doc_before_save()
		old_status = previous.dispatch_status if previous else C.PENDING
		new_status = self.dispatch_status or C.PENDING

		if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
			frappe.throw(
				_("Dispatch status cannot change from {0} to {1}.").format(old_status, new_status)
			)

		if new_status == C.DISPATCHED:
			self._validate_dispatch(old_status, previous)
		elif new_status == C.NOT_DELIVERED and not self.expected_delivery_date:
			frappe.throw(_("Enter the new expected delivery date for Not Delivered."))

		if new_status in (C.PICKUP, C.DELIVERED, C.NOT_DELIVERED) and new_status != old_status:
			self.delivery_confirmed_on = now_datetime()
			self.delivery_confirmed_by = frappe.session.user

	def _validate_dispatch(self, old_status, previous):
		if not self.transporter:
			frappe.throw(_("Transporter is required to mark as Dispatched."))
		if not self.expected_delivery:
			frappe.throw(_("Expected Delivery is required to mark as Dispatched."))

		if old_status != C.DISPATCHED:
			self.dispatched_on = now_datetime()
			self.dispatched_by = frappe.session.user

		option_changed = previous is not None and self.expected_delivery != previous.expected_delivery
		date_unchanged = previous is not None and cstr(self.expected_delivery_date) == cstr(
			previous.expected_delivery_date
		)
		if not self.expected_delivery_date or (option_changed and date_unchanged):
			self.expected_delivery_date = add_days(
				getdate(self.dispatched_on), C.EXPECTED_DAYS[self.expected_delivery]
			)

	def on_update(self):
		if frappe.get_meta("Sales Invoice").has_field("dispatch_status"):
			frappe.db.set_value(
				"Sales Invoice",
				self.sales_invoice,
				"dispatch_status",
				self.dispatch_status,
				update_modified=False,
			)

		if self.dispatch_status == C.DISPATCHED and self._transport_changed():
			from chundakadan.dispatch.sync import sync_transport

			sync_transport(self)

	def _transport_changed(self):
		previous = self.get_doc_before_save()
		if not previous or previous.dispatch_status != C.DISPATCHED:
			return True
		return any(cstr(self.get(f)) != cstr(previous.get(f)) for f in C.TRANSPORT_FIELDS)
