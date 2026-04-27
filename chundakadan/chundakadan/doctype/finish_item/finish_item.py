import frappe
from frappe import _
from frappe.model.document import Document

class FinishItem(Document):
	def validate(self):
		self.validate_unique_finish_per_group()

	def validate_unique_finish_per_group(self):
		if not self.finish or not self.item_group:
			return

		# Check if another record with the same finish and item_group exists
		duplicate = frappe.db.exists(
			"Finish Item",
			{
				"finish": self.finish,
				"item_group": self.item_group,
				"name": ["!=", self.name]
			}
		)

		if duplicate:
			frappe.throw(
				_("Finish '{0}' already exists for Item Group '{1}'").format(
					self.finish, self.item_group
				)
			)
