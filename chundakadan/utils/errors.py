"""Writing to the Error Log from inside an except block.

`frappe.log_error(title, message)` takes the TITLE first, and the title
holds 140 characters. Several handlers here passed the whole failure
sentence first -- "sendmail failed for Leave Application X (created) ->
somebody: <the exception>" -- so the Error Log insert itself threw
CharacterLengthExceededError. Thrown from inside the handler, that undid
the very thing the handler existed to protect: on 2026-11-17, with outgoing
mail switched off, nobody could save a Leave Application.

A log call in a failure path has one job and must not be able to fail the
request, so it goes through here.
"""

import frappe
from frappe.utils import cstr

TITLE_LENGTH = 140


def log_failure(title, detail=None):
	"""Record a failure. Never raises.

	`title` is short and the same for every occurrence, so the Error Log
	groups them; what varies -- names, the exception text -- goes in
	`detail`, followed by the traceback.
	"""
	try:
		traceback = frappe.get_traceback()
		body = f"{detail}\n\n{traceback}" if detail else traceback
		frappe.log_error(title=cstr(title)[:TITLE_LENGTH], message=body)
	except Exception:
		# the log is a courtesy; the caller's work is not
		frappe.logger().error(f"could not write Error Log entry: {cstr(title)[:TITLE_LENGTH]}")
