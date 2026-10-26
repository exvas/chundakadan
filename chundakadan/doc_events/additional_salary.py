"""Additional Salary: the Amount must equal the days still listed under it.

"Fetch Late Arrival Deduction" fills the Late Entry Details table and sets the
Amount to its total. HR may then drop a day that should not be cut — an
approved late arrival. Doing that in the browser updates the Amount, but the
browser is not where the figure has to be right: a stale script, a cached
bundle or a row removed through some other path would leave an Amount that no
longer matches the days printed beneath it, and nobody reading the document
afterwards could tell.

So the total is recomputed on every save. The table is the record of what is
being cut, and the Amount is only its sum.
"""

import re

import frappe
from frappe import _
from frappe.utils import cint, flt

LATE_COMPONENT = "Late Arrival Deduction"
TABLE = "custom_late_entry_details"
REASON_PREFIX = "Late entry deduction"
PERIOD = re.compile(r"(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})")


def sync_late_entry_total(doc, method=None):
	if doc.get("salary_component") != LATE_COMPONENT:
		return

	rows = doc.get(TABLE) or []
	reason = (doc.get("custom_reason") or "").strip()
	if not rows and not reason.startswith(REASON_PREFIX):
		# a Late Arrival Deduction entered by hand, never fetched — the amount
		# is the user's own and nothing here knows better
		return

	doc.amount = round(sum(flt(r.deduction) for r in rows))

	# restate the counts, keeping the period the fetch recorded
	period = PERIOD.search(reason)
	if period:
		doc.custom_reason = _("Late entry deduction {0} to {1}: {2} late min over {3} day(s)").format(
			period.group(1),
			period.group(2),
			sum(cint(r.late_minutes) for r in rows),
			len(rows),
		)
