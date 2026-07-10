# Employee → User provisioning & auto-triggers

**Strict reference for how a login is created from an Employee, and what fires automatically.**
Source of truth: this app (`chundakadan`). Verified against live prod `erp.chundakadan.in`.

> **The one rule.** There is no background job that turns Employees into logins.
> A login exists only when HR runs **Employee → HR Actions → "Create User & Setup"**.
> A fixed chain of side-effects then runs off the employee's **department** and **designation**.

---

## 1. The click and the chain it triggers

`HR Actions → Create User & Setup` → `employee_user_actions.create_user_for_employee()`.
These run automatically, in order, in one transaction:

1. **Permission gate** — only `HR Manager` / `HR User` / `System Manager` / `Administrator`.
2. **Resolve email** — dialog value, else `Employee.company_email`, else `personal_email` (an existing unlinked User is re-used + re-enabled).
3. **Create User + Role Profile** — a `System User` with `role_profile_name` **derived from DEPARTMENT** (see §2).
4. **Link** — stamp `Employee.user_id`.
5. **User Permissions** — normal staff → restricted to own `Employee` (+ `Company` if multi-company). HR/GM dept **or** manager-type designation → **not** restricted (stale self-restriction removed).
6. **Sales Person + MOP** — *if Sales/Marketing dept*: create/enable `Sales Person` + Cash/Cheque rows.
7. **manager_details** — *if manager designation*: add to `Chundakadan Settings.manager_details`.
8. **Welcome email + audit** — optional password-setup email; always an Info-comment listing every step.

---

## 2. Department → Role Profile (`DEPT_TO_STRUCTURE`)

Department name has its ` - ABBR` suffix stripped, then matched exactly, else by case-insensitive substring. Same map used by Employee Transfer.

| Department (base) | Role Profile | Salary Structure |
|---|---|---|
| Sales& Marketing | CDN Sales Executive | CDN Sales Executive Structure |
| HR · HR Coordinator | CDN HR Assistant | CDN Office Staff Structure |
| Accountant | CDN Accountant | CDN Office Staff Structure |
| Purchase | CDN Purchaser | CDN Office Staff Structure |
| billing | CDN Billing | CDN Office Staff Structure |
| Dispatch | CDN Dispatch | CDN Floor Structure |
| General Manager | CDN GM | CDN Management Structure |
| *no match* | *none* | user created without a profile |

> **⚠ GAP — no HOD/manager row.** A department **head** gets their department's *rank-and-file* profile (a Marketing HOD lands on `CDN Sales Executive`, same as the reps). The HOD profile (`CDN Sales HOD`, which carries `Sales HOD Leave Approver`) is **never** assigned automatically — HR must change the Role Profile by hand. This is why a Marketing head can be unable to approve their team's leave.

---

## 3. Two axes (read together)

| | **Department** decides *who you are* | **Designation** decides *how leave routes* |
|---|---|---|
| Drives | Role Profile (roles + modules), salary structure, Sales Person, permission-restrict | Leave-approval chain, manager auto-detection, feeds permission-restrict |
| Logic | `DEPT_TO_STRUCTURE` (`employee_transfer.py`) | `generate_approval_flow` (`api/leave.py`) |

> **⚠ The mismatch.** Leave *routing* is by **designation**; the *role that lets you approve* comes from the **department-based Role Profile**. A person can route correctly yet lack the role to act. Fixing a routing problem often means touching **both** the designation and the Role Profile.

### Designation → leave chain

| Designation | Chain |
|---|---|
| Sales Executive · Business Development Executive · BDE | Sales HOD → HR → GM |
| Accountant · Purchase Coordinator · Purchaser | Accounts Manager → HR → GM |
| Area Sales Manager · Accounts Manager · Sales& Marketing Manager · Deputy Sales & Marketing Manager | HR → GM |
| HR Coordinator · Coordinator · HR Associate | GM only |
| General Manager | HR only |
| *anything else (default)* | HR → GM |

---

## 4. Role Profiles are code, not data

Profiles live in `seed/role_profiles.py` (`PROFILES`, 15 profiles) and are **re-synced on every `bench migrate`** (`before_migrate` → `seed_profiles` → `_ensure_role_profile`, which **clears + rewrites** a profile's roles to match code when they differ).

- **⚠ Editing a profile's roles in the desk UI is reverted on the next migrate.** Durable role changes must be made in `seed/role_profiles.py`.
- **User→profile *assignments* survive migrate** (only the profile definition is synced). Assignments are set at Create-User time or by the manual `apply_user_assignments`.

| Role Profile | Leave-approval roles |
|---|---|
| CDN Sales Executive | Leave Approver |
| CDN Sales HOD | Leave Approver · **Sales HOD Leave Approver** |
| CDN Sales Admin | Leave Approver · **Sales HOD Leave Approver** |
| CDN HR Manager | Leave Approver · **HR Leave Approver** · Expense Approver |
| CDN HR Assistant | Leave Approver · **HR Leave Approver** |
| CDN GM | Leave Approver · **GM Leave Approver** |

---

## 5. HR Actions reference

All on the Employee form (HR Actions / Setup Dashboard), HR-gated, idempotent, audit-logged. All in `employee_user_actions.py`.

| Button | What it does |
|---|---|
| Create User & Setup | The full §1 chain. |
| Setup Dashboard | One dialog, ✓/✗ for user, permissions, sales person, geofence, leave allocation, shift, salary structure, reports-to, manager_details — with inline fixes. |
| Apply Permissions | Re-derive & apply the User-Permission set (fixes a promoted staffer still self-restricted). |
| Setup Sales Person | Create/repair Sales Person + MOP rows. |
| Apply Geofence | Set/clear `shift_location` on active Shift Assignments. |
| Reset Password | Set directly, or email a reset link. |
| Disable User (Exit Employee) | Disable user · revoke sessions · Employee = Left · disable Sales Person · drop from manager_details. |
| Re-enable User | Re-hire: re-enable user · Employee = Active · re-enable Sales Person. |
| Send Re-Login Reminder | Push a mobile notification to log out/in so cached config refreshes. |
| Allocate Annual Leaves | Run annual allocation for one employee. |

> **Promotions need a re-run.** Department/designation are read *when a button runs*. Promoting someone does **not** self-update their profile/permissions — HR must change the Role Profile and re-run **Apply Permissions** / Setup Dashboard.

---

## 6. Where this lives in code

| File | Role |
|---|---|
| `chundakadan/api/employee_user_actions.py` | HR Actions + Create-User chain |
| `doc_events/employee_transfer.py` | `DEPT_TO_STRUCTURE` map |
| `seed/role_profiles.py` | profile definitions + migrate sync + `apply_user_assignments` |
| `chundakadan/api/leave.py` | `generate_approval_flow` (designation → chain) |
| `public/js/employee.js` | the HR Actions buttons |
| `hooks.py` | `before_migrate → seed_profiles` |
