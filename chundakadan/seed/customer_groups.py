"""The two customer groups this business uses, created when they can be.

They used to ship as a fixture. A fixture is imported during
``bench install-app``, and each one names ``All Customer Groups`` as its
parent — but that root is created by **ERPNext's setup wizard**, not by
installing ERPNext. On a site where the wizard has not run (every CI site,
and any freshly rebuilt one) the parent is absent, and the nested-set code
reads its bounds as None:

    TypeError: cannot unpack non-iterable NoneType object

which aborts the whole install of this app.

So they are seeded instead: created when the root is there, skipped quietly
when it is not, and never touched once they exist — a group the business has
renamed or re-parented is theirs.
"""

import frappe

ROOT = "All Customer Groups"
GROUPS = ("Dealer", "Retail Outlet")


def ensure_customer_groups():
	"""after_migrate: the groups exist, if this site is set up enough to hold them."""
	if not frappe.db.exists("Customer Group", ROOT):
		# ERPNext's setup wizard has not run here; there is no tree to hang them on
		return

	for name in GROUPS:
		if frappe.db.exists("Customer Group", name):
			continue
		try:
			frappe.get_doc(
				{
					"doctype": "Customer Group",
					"customer_group_name": name,
					"parent_customer_group": ROOT,
					"is_group": 0,
				}
			).insert(ignore_permissions=True)
			print(f"chundakadan: created Customer Group {name}")
		except Exception as e:
			print(f"chundakadan: could not create Customer Group {name}: {e}")
