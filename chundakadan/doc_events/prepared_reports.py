"""Keep every report running in the foreground.

Frappe turns a Script Report into a Prepared (background) Report as soon as
one run crosses 15 seconds, and the report then only shows data after the
user clicks "Generate New Report". The business wants reports to open
directly, so we clear the flag and switch off the automation that sets it.

Standard reports are re-synced from the app on every migrate, which resets
these fields - that is why this runs as an after_migrate hook.
"""

import frappe


def ensure_prepared_reports_disabled(*args, **kwargs):
	meta = frappe.get_meta("Report")
	fields = {}
	if meta.has_field("prepared_report"):
		fields["prepared_report"] = 0
	if meta.has_field("disable_prepared_report_automation"):
		fields["disable_prepared_report_automation"] = 1
	if not fields:
		return 0

	# a report needs fixing when EITHER field is wrong
	names = frappe.get_all(
		"Report",
		or_filters=[[field, "!=", value] for field, value in fields.items()],
		pluck="name",
	)
	for name in names:
		frappe.db.set_value("Report", name, fields, update_modified=False)

	if names:
		frappe.clear_cache()
	frappe.db.commit()
	return len(names)
