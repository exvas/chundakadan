# Idempotent setup for the public Privacy Policy Web Page.
#
# Runs from the install/migrate hook OR can be invoked manually via
# `bench --site <site> execute chundakadan.seed.privacy_policy.upsert_page`.
#
# Apple App Store review REQUIRES a working Privacy Policy URL — this
# creates the page at /privacy-policy on the site (e.g.
# https://erp.chundakadan.in/privacy-policy) so the App Store Connect
# Privacy Policy URL field has somewhere to point.

import frappe


ROUTE = "privacy-policy"
TITLE = "Privacy Policy"


HTML_BODY = """<style>
.policy-wrap { max-width: 760px; margin: 0 auto; padding: 32px 24px 80px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #1a1a1a; line-height: 1.65; }
.policy-wrap h1 { font-size: 32px; margin: 0 0 8px; color: #1a1a1a; }
.policy-wrap .updated { color: #888; font-size: 14px; margin-bottom: 32px; }
.policy-wrap h2 { font-size: 22px; margin: 32px 0 12px; color: #1a1a1a; border-bottom: 1px solid #eee; padding-bottom: 6px; }
.policy-wrap h3 { font-size: 17px; margin: 20px 0 8px; color: #333; }
.policy-wrap p { margin: 0 0 14px; }
.policy-wrap ul { margin: 0 0 14px; padding-left: 22px; }
.policy-wrap li { margin: 4px 0; }
.policy-wrap a { color: #b8860b; text-decoration: none; }
.policy-wrap a:hover { text-decoration: underline; }
.policy-wrap .footer { margin-top: 48px; padding-top: 24px; border-top: 1px solid #eee; color: #666; font-size: 14px; }
</style>

<div class="policy-wrap">

<h1>Privacy Policy</h1>
<div class="updated">Last updated: 4 June 2026</div>

<p>This Privacy Policy describes how <strong>Chundakadan Agencies</strong> ("we", "us", "our") collects, uses, and discloses information through the Chundakadan App (the "App"). The App is for internal use by Chundakadan Agencies employees and authorised contractors only.</p>

<h2>1. Information We Collect</h2>

<h3>Account Information</h3>
<ul>
  <li><strong>Email address</strong> — used as your login identifier</li>
  <li><strong>Name, designation, employee ID</strong> — linked to your ERPNext Employee record</li>
</ul>

<h3>Location Data</h3>
<ul>
  <li><strong>Precise GPS location</strong> — captured when you check in / out, log a customer visit, or create a sales order. Used to verify on-site presence and track customer-visit history.</li>
  <li>Stored against your Employee record in our private ERPNext server.</li>
  <li>NOT shared with any third party.</li>
  <li>NOT used for advertising or personal profiling.</li>
</ul>

<h3>Device Information</h3>
<ul>
  <li><strong>Push notification token (FCM)</strong> — used to deliver HR Policy updates, Newsletter posts, and leave-application status changes.</li>
  <li><strong>Device platform</strong> (Android / iOS) and last-seen timestamp — for sending platform-appropriate notifications.</li>
</ul>

<h3>Usage Data</h3>
<ul>
  <li><strong>Activity logs</strong> — which records you create, edit, or submit (sales orders, visit logs, payment entries, leave applications). Stored against your user account in ERPNext and used for performance reporting.</li>
</ul>

<h2>2. How We Use Information</h2>
<ul>
  <li>To enable check-in / attendance tracking</li>
  <li>To log customer visits and their geographic context</li>
  <li>To create and route business documents (sales orders, payment entries, leave applications) through internal approval workflows</li>
  <li>To deliver in-app notifications about HR policies, newsletters, and approval decisions</li>
  <li>To generate sales and operations reports for management</li>
</ul>

<h2>3. Sharing of Information</h2>
<p>We do <strong>NOT</strong> sell or share your information with third parties for advertising, marketing, or analytics outside our company.</p>

<p>We use the following third-party services strictly to operate the App:</p>
<ul>
  <li><strong>Google Firebase Cloud Messaging</strong> — push notification delivery (<a href="https://policies.google.com/privacy" target="_blank">Google's privacy policy</a>)</li>
  <li><strong>OpenStreetMap Nominatim</strong> — reverse-geocoding GPS coordinates into human-readable addresses</li>
  <li><strong>Frappe Cloud</strong> (or self-hosted server) — backend database and APIs</li>
</ul>

<p>Within Chundakadan Agencies, your data is accessible to:</p>
<ul>
  <li>Your direct manager and HOD</li>
  <li>HR team</li>
  <li>Senior management (GM, MD)</li>
  <li>The IT/system administrator</li>
</ul>

<h2>4. Data Retention</h2>
<ul>
  <li><strong>Active employees:</strong> data retained for the duration of your employment</li>
  <li><strong>Resigned/terminated employees:</strong> account disabled within 7 days of last working day; data retained for 7 years per Indian labour-law record-keeping requirements, then permanently deleted</li>
</ul>

<h2>5. Your Rights</h2>
<p>You may request:</p>
<ul>
  <li>A copy of all data we hold about you</li>
  <li>Correction of inaccurate data</li>
  <li>Deletion of your account upon resignation (subject to the retention requirements above)</li>
</ul>
<p>Send requests to <a href="mailto:sales@chundakadan.in">sales@chundakadan.in</a> with subject "Data Privacy Request".</p>

<h2>6. Children's Privacy</h2>
<p>This app is for adult employees of Chundakadan Agencies. We do not knowingly collect data from anyone under 18.</p>

<h2>7. Security</h2>
<ul>
  <li>All communication between the App and our servers is encrypted with TLS 1.2+</li>
  <li>Authentication tokens are stored in the device's secure keychain (iOS) or encrypted shared preferences (Android)</li>
  <li>No passwords are stored on the device</li>
  <li>Backend servers are firewalled and access-restricted</li>
</ul>

<h2>8. Changes to This Policy</h2>
<p>We may update this Privacy Policy. Material changes will be notified to all active employees via in-app notification at least 7 days before taking effect.</p>

<h2>9. Contact</h2>
<p>
  <strong>Chundakadan Agencies</strong><br>
  Calicut, Kerala, India<br>
  Email: <a href="mailto:sales@chundakadan.in">sales@chundakadan.in</a>
</p>

<div class="footer">
  This page exists to satisfy the privacy-policy URL requirement of Apple App Store and Google Play submissions. For internal HR-related queries please use the in-app HR Policy page or contact HR directly.
</div>

</div>
"""


def upsert_page():
    """Create or update the Privacy Policy Web Page at /privacy-policy.

    Idempotent — safe to run on every migrate. Updates the HTML body
    in place if the page already exists.
    """
    existing = frappe.db.exists("Web Page", {"route": ROUTE})
    if existing:
        doc = frappe.get_doc("Web Page", existing)
        doc.title = TITLE
        doc.main_section = HTML_BODY
        doc.published = 1
        doc.content_type = "HTML"
        doc.show_title = 0  # we render our own <h1>
        doc.show_sidebar = 0
        doc.flags.ignore_permissions = True
        doc.save()
        print(f"chundakadan.seed.privacy_policy: updated existing Web Page '{existing}'")
        return existing

    doc = frappe.get_doc({
        "doctype": "Web Page",
        "title": TITLE,
        "route": ROUTE,
        "published": 1,
        "content_type": "HTML",
        "main_section": HTML_BODY,
        "show_title": 0,
        "show_sidebar": 0,
        "meta_title": "Chundakadan App — Privacy Policy",
        "meta_description": (
            "How Chundakadan Agencies collects, uses, and discloses "
            "information through the Chundakadan App. For internal "
            "employee use only."
        ),
    })
    doc.flags.ignore_permissions = True
    doc.insert()
    print(f"chundakadan.seed.privacy_policy: created Web Page '{doc.name}' at /{ROUTE}")
    return doc.name
