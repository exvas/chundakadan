# Chundakadan HR + Payroll Runbook

Single-page reference for HR's monthly workflow. Last verified 2026-06-05.

---

## Monthly cycle at a glance

| Day of month | What | Who | Time |
|---|---|---|---|
| 1st – last | Daily attendance accumulates from mobile Check-In/Out | Auto | n/a |
| 25th | Reminder: cut-off for previous month's leave + adjustments | HR | 5 min |
| 26th – 30th | Review attendance + leave records for previous month | HR | 30 min |
| 1st of next month | Run Payroll Entry for previous month | HR | 20 min |
| 2nd – 5th | Make Bank Entry, hand out cash slips | HR + Accounts | 30 min |
| 5th – 7th | Salary credited / cash collected | Employees | n/a |

---

## 1 · Daily attendance — fully automated

Sales executives + floor staff Check-In / Check-Out from the mobile app. The mobile call:

- Creates an `Employee Checkin` (counts toward Attendance)
- Creates a paired `Customer Visit Log` (visit_type = Check-In or Check-Out)
- Reverse-geocodes the GPS coordinates → `custom_location` (street address)

ERPNext's auto-attendance cron runs nightly and pairs IN/OUT into one `Attendance` row per employee per day. Nothing for HR to do.

**Manual entry exception:** for employees who don't have a mobile (HOD / back-office), HR enters Check-Ins directly via `/app/employee-checkin → New` with `Device ID = HOD` and `Skip Auto Attendance = ✓` (so the manual rows don't break the cron's pairing logic).

---

## 2 · Leave management

### Approval workflow (4-step chain)

```
Sales Executive applies for leave on mobile
   → Sales HOD (Arjun for Marketing, Razeel for Northern)
       → HR (Bindu primary / Nakshathra backup)
           → GM (Najeeb) submits — leave goes from Draft → Submitted
```

Each step:
- The current approver gets a push notification on their phone
- Bell icon shows the pending leave with a red badge
- Tap → opens the Leave Application detail → Approve / Reject

**Special-case roles** (any can approve at any step via the widened gate):
- HR Leave Approver: Bindu, Nakshathra
- GM Leave Approver: Najeeb
- Sales HOD Leave Approver: Arjun, Razeel
- Accounts Manager Leave Approver: Abdul Rashid

Custom code in `chundakadan/chundakadan/api/leave.py` enforces this. Audit trail (`current_approver`, `approval_flow`) is stamped on every step before any session-elevation.

### Annual leave allocation

Cron in chundakadan fires once a year (set in Chundakadan Settings.`annual_allocation_run_date`, currently **31-12-2026**) and creates Leave Allocation records for every active employee against the Annual Leave Policy (`HR-LPOL-2025-00001`).

To manually re-allocate (e.g., for a new joiner mid-year):
```
/app/leave-allocation → New
  Employee: <name>
  Leave Type: <type>
  From Date / To Date: current Leave Period dates
  New Leaves Allocated: <prorated>
```

### Conflict resolution

When a leave is approved and the employee already has Attendance records for those days, chundakadan's `before_validate` hook automatically converts `Present` / `WFH` rows to `On Leave`. No manual cleanup needed.

---

## 3 · Monthly Payroll Entry

Run this on the 1st of each month for the previous month.

### Step-by-step

1. **Open** `/app/payroll-entry` → **New Payroll Entry**

2. **Fill the form:**
   - Posting Date: today
   - Company: Chundakadan Agencies
   - Payroll Frequency: Monthly
   - Start Date: `YYYY-MM-01`, End Date: `YYYY-MM-{last day}`
   - Payroll Period: auto-filled to `FY 2026-27` (or current FY)
   - Branch (optional): leave blank to include all branches
   - Department (optional): leave blank to include all

3. **Click "Get Employees"** — pulls every employee with an active Salary Structure Assignment within the date range. Expected: 28 (or however many are currently assigned).

4. **Review the employee list** — uncheck any employee you want to exclude this month (e.g., on long leave without pay).

5. **Click "Create Salary Slip"** — generates a draft Salary Slip per included employee. Takes ~30 seconds.

6. **Spot-check 2-3 slips** by opening them. Verify earnings + deductions look right. Check if leave deductions applied correctly for absent days.

7. **Back on the Payroll Entry**, click **"Submit Salary Slips"** — submits all drafts.

8. **Click "Make Bank Entry"** — generates one consolidated Payment Entry for all bank-mode employees. Their salaries are debited from Federal Bank account in one go.

9. **For cash-mode employees** — print individual Salary Slips:
   - Open each Cash-mode slip
   - Print → hand to employee → collect signature

### Editing a specific Salary Slip before submit

A few employees might need adjustments (bonuses, deductions, advances). On the draft Salary Slip:
- Earnings → add row: `Component = Bonus`, `Amount = <amount>`
- Deductions → add row: `Component = Employee Advance Recovery`, `Amount = <amount>`
- Save (still Draft) → resubmit via Payroll Entry

---

## 4 · Bank disbursement

After "Make Bank Entry":
1. **/app/payment-entry** → find the new Payment Entry (linked to the Payroll Entry)
2. Verify each employee's name + amount + bank account
3. Submit the Payment Entry — debits the Federal Bank account
4. Generate a **Bank Remittance** file:
   - **/app/bank-remittance** → New → select the Payment Entry
   - Choose Bank: Federal Bank → Generate
   - Download the NEFT batch file → upload to Federal Bank's portal

Bank processes overnight; employees receive their salary the next morning.

---

## 5 · New joiner onboarding

When HR creates a new employee:

1. **/app/employee** → New Employee → fill basics (Name, DoB, DoJ, Department, Designation, Branch)
2. **Salary Mode** dropdown (Cash / Bank Transfer / Cheque)
3. If Bank Transfer: fill Bank Name, A/C No, IFSC
4. Optionally fill UAN if you start filing PF returns
5. Save → an Employee ID is auto-generated (e.g. `CDN/026/045`)

Then in `chundakadan/chundakadan/seed/role_profiles.py`:
- Add the new user's email to `USER_PROFILE_MAP` with the right CDN profile
- Commit + push + `bench migrate` + run `apply_user_assignments`

Finally:
1. **/app/leave-allocation** → New → allocate annual leave (prorated by joining date)
2. **/app/salary-structure-assignment** → New → assign the right Salary Structure with their base salary
3. **/app/user** → set Role Profile + Module Profile (or wait for the script to do it on next migrate)

---

## 6 · Common issues + fixes

| Issue | Fix |
|---|---|
| Employee missing from "Get Employees" in Payroll Entry | Check Salary Structure Assignment exists + submitted + Effective From ≤ start date |
| Salary Slip shows wrong Basic Salary | Salary Structure formula or Salary Structure Assignment base salary needs updating |
| Bank Entry skips an employee | They probably have `custom_salary_mode = Cash` — that's correct, Bank Entry only includes Bank Transfer mode |
| Mobile Check-In not creating Attendance | Auto-attendance cron runs nightly — check tomorrow. If still missing, the Shift Type isn't set on the Employee |
| Leave Application shows "Not permitted" | Approver is missing the canonical Leave Approver role — see `project_chundakadan_leave_approval.md` memory |
| Push notification not arriving | Check `/app/fcm-token` has a row for that user; if empty, they need to log in to the V1.3.2+ APK |

---

## 7 · Where things live (for IT)

| What | Where |
|---|---|
| Leave approval logic | `chundakadan/chundakadan/api/leave.py` |
| Push notification helper | `chundakadan/chundakadan/utils/push.py` |
| Custom Fields installer | `chundakadan/chundakadan/install.py` |
| Role Profiles definition | `chundakadan/chundakadan/seed/role_profiles.py` |
| Payroll Period auto-create | `chundakadan/chundakadan/seed/payroll_period.py` |
| Privacy Policy page source | `chundakadan/chundakadan/seed/privacy_policy.py` |
| Mobile API endpoints | `field_sales/field_sales/Api/auth.py` |

Source of truth is always the Python file. Don't edit Custom Fields / Role Profiles / Web Pages directly in the desk — the next `bench migrate` will overwrite manual changes.

---

## 8 · Quick console commands (bench --site erp.chundakadan.in console)

```python
# Re-sync all 15 Role Profiles to current spec
from chundakadan.seed.role_profiles import seed_profiles
seed_profiles()

# Re-apply USER_PROFILE_MAP (strips + re-adds roles per spec)
from chundakadan.seed.role_profiles import apply_user_assignments
apply_user_assignments()

# Audit user-profile state
from chundakadan.seed.role_profiles import audit
audit()

# Push a test notification
from chundakadan.utils.push import send_to_users
send_to_users(["gm@chundakadan.in"], "Test", "Test push", {"route": "/hr_policy"})

# Backfill missing reverse-geocoded addresses (slow, 1 req/sec)
from chundakadan.utils.geocode import backfill_synchronously
backfill_synchronously("Customer Visit Log", lat_field="latitude", lon_field="longitude")
```
