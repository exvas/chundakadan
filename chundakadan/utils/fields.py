"""Did this field really change?

A plain `!=` between a document and `get_doc_before_save()` says yes far
too often. A Datetime comes back from a form as the string
"2026-10-05 10:00:00" while the saved document holds a datetime object;
None and "" are both empty but are not equal; a Float read as 0 is not
the string "0". Every guard that refuses an edit on "this field changed"
has to compare like with like, or it refuses edits nobody made.

This cost the office a day: an accountant could not correct a valuation
rate on an approved Item because Approved On "changed" (commit 0722cd0).
The same shape of guard sits on Customer and on Daily Work Summary.
"""

import frappe
from frappe.utils import cstr, flt, get_datetime, getdate


def field_changed(doctype: str, doc, before, fieldname: str) -> bool:
	"""True only when the value genuinely differs."""
	new, old = doc.get(fieldname), before.get(fieldname)
	if not new and not old:
		# None, "", 0 and 0.0 are all "nothing was filled in"
		return False

	field = frappe.get_meta(doctype).get_field(fieldname)
	fieldtype = field.fieldtype if field else None
	try:
		if fieldtype == "Datetime":
			return get_datetime(new) != get_datetime(old)
		if fieldtype == "Date":
			return getdate(new) != getdate(old)
		if fieldtype in ("Currency", "Float", "Percent"):
			return flt(new, 6) != flt(old, 6)
		if fieldtype in ("Int", "Check"):
			return int(new or 0) != int(old or 0)
	except Exception:
		# a value that will not parse is a real change -- let the guard speak
		return True
	return cstr(new) != cstr(old)
