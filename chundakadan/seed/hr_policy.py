# Copyright (c) 2026, Chundakadan
# One-shot seed for the HR Policy Single doctype + a sample Newsletter.
#
# Run on the VPS:
#   bench --site erp.chundakadan.in execute chundakadan.seed.hr_policy.seed_policy
#   bench --site erp.chundakadan.in execute chundakadan.seed.hr_policy.seed_test_newsletter
#
# Idempotent — running again just overwrites with the same content.

import os

import frappe
from frappe import _


def _read_html_file(filename):
    here = os.path.dirname(__file__)
    with open(os.path.join(here, filename), "r", encoding="utf-8") as f:
        return f.read()


def seed_policy():
    """Load chundakadan/seed/cdn_policy.html into HR Policy.policy_html
    and save. on_update hook will fire the 'HR Policy Updated' push to
    every Active employee.
    """
    html = _read_html_file("cdn_policy.html")
    doc = frappe.get_single("HR Policy")
    doc.policy_html = html
    # First-time save without a PDF — uncheck notify if you want to
    # avoid pinging everyone during initial setup. Default is on.
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()
    print(f"✓ HR Policy seeded — version {doc.version}, "
          f"{len(html)} characters of HTML.")
    return {"version": doc.version, "html_length": len(html)}


def seed_test_newsletter():
    """Create a sample Newsletter so HR can verify the mobile push +
    listing work end-to-end. Safe to run repeatedly — creates a new
    Newsletter each time (Frappe auto-names them).
    """
    subject = "Welcome to the Chundakadan Mobile App"
    message = """
    <h2>👋 Welcome to the new Chundakadan mobile app!</h2>
    <p>Hello team,</p>
    <p>This is a test newsletter to confirm the in-app Newsletter
    feature is working. Going forward, HR and Management will use this
    channel to share company updates with everyone on the field and
    in the office.</p>

    <h3>What you'll receive here</h3>
    <ul>
      <li>Holiday announcements</li>
      <li>Policy updates and reminders</li>
      <li>Company news and recognitions</li>
      <li>Important operational notices</li>
    </ul>

    <h3>How it works</h3>
    <ol>
      <li>HR creates a Newsletter on the ERP.</li>
      <li>You get a push notification on your phone within seconds.</li>
      <li>Tap the notification — the newsletter opens in the app.</li>
      <li>You can also open it any time from the <strong>Newsletter</strong>
          tile on the home screen.</li>
    </ol>

    <p>If you're reading this on the mobile app — the system is working
    correctly. 🎉</p>

    <p>Stay tuned for more updates.</p>

    <p>— Chundakadan HR</p>
    """

    doc = frappe.get_doc({
        "doctype": "Newsletter",
        "subject": subject,
        "sender_name": "Chundakadan HR",
        "sender_email": frappe.session.user if frappe.session.user != "Guest"
                        else "noreply@chundakadan.in",
        "message": message,
    })
    doc.flags.ignore_permissions = True
    doc.insert()
    frappe.db.commit()
    print(f"✓ Test Newsletter created: {doc.name}")
    print(f"  Subject: {subject}")
    print(f"  Mobile push will fire via the after_insert hook for every "
          f"Active employee.")
    return {"name": doc.name, "subject": subject}
