# Employee Onboarding — Quick Guide

A simple checklist for HR to add a new employee to ERPNext (`erp.chundakadan.in`).
*Estimated time per employee: 5–10 minutes.*

---

## Step 1 — Create the User account

This is the employee's login.

1. Open `/app/user/new`
2. Fill **Email** (their work email — e.g. `firstname@chundakadan.in`)
3. Fill **First Name** (and Last Name if you want)
4. Untick **Send Welcome Email** if you'll share credentials manually
5. **Save**
6. Set a password: on the User form, click **Password → Set Password**

---

## Step 2 — Create the Employee record

This is where HR data lives. ALL fields marked below are **mandatory** — the form won't save without them.

1. Open `/app/employee/new`
2. Fill these in order:

   | Field | Notes |
   |---|---|
   | **First Name** ⭐ | As per ID proof |
   | **Gender** ⭐ | Male / Female / Other |
   | **Date of Birth** ⭐ | |
   | **Date of Joining** ⭐ | Today or actual joining date |
   | **Company** ⭐ | Chundakadan Agencies (or your company) |
   | **Status** ⭐ | Active |
   | **User ID** ⭐ | Pick the User you created in Step 1 |
   | **Designation** ⭐ | See list below |
   | **Department** ⭐ | e.g. Sales & Marketing, HR & Administration |
   | **Holiday List** ⭐ | The current year's holiday calendar |

3. **Save**

### Allowed designations (case-sensitive)

These plug into the leave approval chain automatically:

- **Sales Executive** → approver chain: ASM → HR → GM
- **Area Sales Manager** → HR → GM
- **Accounts Manager** → HR → GM
- **Accountant** → Accounts Manager → HR → GM
- **Purchase Coordinator** → Accounts Manager → HR → GM
- **HR Coordinator** / **Coordinator** / **HR Associate** → GM only
- **General Manager** → HR only
- Anything else → default HR → GM

---

## Step 3 — Is this person a Sales Executive?

**If YES**, do this extra step so they can use the mobile app for sales:

1. Open `/app/sales-person/new`
2. **Sales Person Name** = employee's name
3. **Employee** = the Employee you created
4. **Parent Sales Person** = `Sales Team`
5. **Enabled** = ticked
6. **Save**

Then in **Chundakadan Settings → Sales Person Mode of Payment Mapping**, add two rows:
- (Sales Person, Company, **Cash**, account `1110 - Cash - CA`)
- (Sales Person, Company, **Cheque**, account `1201 - Federal-Bank Account - CA`)

This is what makes Payment Entry work for them on mobile.

---

## Step 4 — Is this person a Manager?

**If YES** (Area Sales Manager, GM, HR Coordinator, etc., who needs to oversee everyone):

1. Open `/app/chundakadan-settings → Manager Details`
2. Add a row with:
   - **Employee** = the Employee record
   - Tick **Allow Edit** / **Allow Submit** / **Workflow Approval** as appropriate
3. **Save**

This gives them view-all visibility on the mobile across every sales person.

---

## Step 5 — Is this person a Leave Approver?

**If YES** (HR, GM, ASM, Accounts Manager — anyone who signs off leaves):

Assign one of these roles on their User record:

- **HR Leave Approver** → for HR Coordinator
- **GM Leave Approver** → for General Manager
- **ASM Leave Approver** → for Area Sales Manager
- **Accounts Manager Leave Approver** → for Accounts Manager

Steps:
1. Open `/app/user/<their email>`
2. In the **Roles** section, search for the role above and tick it
3. **Save**

---

## Step 6 — Hand them the mobile app

1. Send them the latest APK file: `chundakadan-release-app-V<version>.apk`
2. They install on Android (Settings → allow install from unknown sources first time)
3. They open the app, log in with the email + password from Step 1
4. Sales tiles show for sales staff; HR-only staff see Attendance / Tasks / Leaves / Payslips / Expenses

---

## What HR sees AFTER onboarding

- The employee shows up in `/app/employee` list
- Their leave applications will be routed to the right approver chain automatically
- They can apply for leave on mobile; **Sick Leave** will require a photo of the medical certificate
- Annual leaves are auto-allocated on the date set in Chundakadan Settings (e.g. April 1)

---

## Common mistakes to avoid

❌ Saving Employee without `User ID` → employee can't log in to mobile.
❌ Wrong `Designation` spelling (e.g., "sales executive" instead of "Sales Executive") → leave routing falls to default HR → GM, skipping ASM.
❌ Forgetting MOP mapping for new Sales Executive → their Payment Entries on mobile will fail with 400.
❌ Creating a Sales Person without an Employee link → mobile login won't resolve them.

---

## Need help

Ping IT / dev team on WhatsApp with:
- Employee name + Employee ID
- Screenshot of the issue
- The URL you're on
