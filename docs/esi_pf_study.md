# ESI + PF — Statutory deductions study for Chundakadan

Pending implementation as of 2026-06-06. Audit revealed broken formulas
in both ESI and PF Salary Components — this doc captures the correct
design before implementing.

---

## ESI (Employees' State Insurance) — India

### Eligibility
- Applies to **establishments with ≥ 10 employees**
- Covers employees earning **gross wages ≤ ₹21,000/month** (₹25,000 for persons with disability)
- Once an employee crosses ₹21,000 in any month, contributions continue till the end of the contribution period (Apr–Sep or Oct–Mar) — chundakadan likely simplifies to "month-by-month check"

### Contribution rates
| Party | Rate | Applied to |
|---|---|---|
| Employee | **0.75%** | gross wages |
| Employer | **3.25%** | gross wages |
| **Total** | **4.00%** | gross wages |

### Chundakadan exposure
Looking at the May 2026 Excel — most security guards earn ₹13K–16.8K, all floor staff and house keeping similarly under ₹21K. **Probably ~50+ employees are ESI-eligible.** Currently every Salary Slip shows ESI = 0 because the formula is broken.

### Correct Salary Component config

**ESI (Employee share — Deduction):**
```python
salary_component: "ESI"
type: "Deduction"
amount_based_on_formula: 1
formula: "round(gross_pay * 0.0075) if gross_pay <= 21000 else 0"
condition: "gross_pay <= 21000"   # extra safety; either condition or formula clause works
round_to_the_nearest_integer: 1
depends_on_payment_days: 1        # prorate if LOP days
```

**ESI Employer (Employer share — Statistical):**
```python
salary_component: "ESI Employer Contribution"
type: "Earning"                   # added as informational, NOT deducted
statistical_component: 1          # excluded from gross pay totals
amount_based_on_formula: 1
formula: "round(gross_pay * 0.0325) if gross_pay <= 21000 else 0"
do_not_include_in_total: 1
round_to_the_nearest_integer: 1
```

The employer share is for reporting (filing ESI returns) — it's a company expense, NOT deducted from the employee. Marking it `statistical_component: 1` keeps it visible on the slip without inflating the gross.

### Filing
- Monthly ESI return filed via [esic.in portal](https://www.esic.in)
- Due by 15th of following month
- Both contributions paid by employer on the portal (employer deducts employee share from salary)

---

## PF (Provident Fund) — India

### Eligibility
- Applies to **establishments with ≥ 20 employees**
- Mandatory for employees earning **Basic + DA ≤ ₹15,000/month** (statutory wage ceiling)
- Above ₹15K → optional (most chundakadan employees probably qualify if basic ≤ 15K)
- Wage ceiling is the cap for contributions; if Basic > ₹15K, contributions are usually computed on ₹15K (or by mutual agreement)

### Contribution rates
| Party | Rate | Goes to |
|---|---|---|
| Employee | **12%** | EPF (Provident Fund) |
| Employer | **12%** | Split: 8.33% to EPS (Pension), 3.67% to EPF |
| Admin charges | 0.5% | EPF Admin |
| EDLI | 0.5% | EDLI (Life Insurance) |

All rates applied to **Basic + DA** (or capped at ₹15K).

### Current broken state
```python
# Current formula:
base * 0.12 / 100   if base <= 10000   else 0
```

For base = ₹15,000, returns **₹18** (should be ₹1,800). The formula was probably written with the intent of "12 / 100" but accidentally typed "0.12 / 100" which is 0.12%. Plus wrong threshold (10K vs 15K).

### Correct Salary Component config

**Employee PF (Deduction):**
```python
salary_component: "Employee PF"
type: "Deduction"
amount_based_on_formula: 1
formula: "round(min(base, 15000) * 0.12)"
round_to_the_nearest_integer: 1
depends_on_payment_days: 1
```

Note: uses `min(base, 15000)` so high-basic employees still contribute on the ₹15K cap if they're in PF.

**PF Employer Contribution (Statistical):**
```python
salary_component: "PF Employer Contribution"
type: "Earning"
statistical_component: 1
amount_based_on_formula: 1
formula: "round(min(base, 15000) * 0.12)"
do_not_include_in_total: 1
round_to_the_nearest_integer: 1
```

### Filing
- Monthly PF return (ECR) filed via [unifiedportal-emp.epfindia.gov.in](https://unifiedportal-emp.epfindia.gov.in)
- Due by 15th of following month
- UAN (Universal Account Number) per employee — captured in our `custom_uan_number` field

---

## Chundakadan-specific decisions needed

Before implementing, confirm with HR:

1. **Is Chundakadan currently registered with ESIC?**
   - If YES → enable the corrected ESI formula immediately
   - If NO but ≥10 employees → registration is mandatory; HR needs to register before deducting
   - If voluntarily opting out → keep ESI=0 (but ESIC may issue penalties)

2. **Is Chundakadan currently registered with EPFO?**
   - If YES → enable corrected PF formula
   - If NO but ≥20 employees → mandatory
   - Has PF Establishment Code been allocated?

3. **For the 47 security guards** — are they on Chundakadan's payroll directly, OR are they on a contractor's payroll (with Chundakadan paying the contractor)?
   - If on contractor's payroll → no Chundakadan ESI/PF liability for them
   - If direct → all 47 need ESI/PF deductions

4. **Salary Component cleanup**:
   - Delete the duplicate "Provident Fund" component (only "Employee PF" should remain)
   - Fix the broken formulas for ESI + Employee PF
   - Add the 2 new Employer Contribution components for reporting

---

## Implementation plan (for tomorrow after confirmation)

### Phase A — fix existing components

Update via `chundakadan/seed/salary_components.py` (new file):

```python
import frappe

COMPONENTS = [
    {
        "name": "ESI",
        "type": "Deduction",
        "amount_based_on_formula": 1,
        "formula": "round(gross_pay * 0.0075) if gross_pay <= 21000 else 0",
        "round_to_the_nearest_integer": 1,
        "depends_on_payment_days": 1,
    },
    {
        "name": "Employee PF",
        "type": "Deduction",
        "amount_based_on_formula": 1,
        "formula": "round(min(base, 15000) * 0.12)",
        "round_to_the_nearest_integer": 1,
        "depends_on_payment_days": 1,
    },
    {
        "name": "ESI Employer Contribution",
        "type": "Earning",
        "statistical_component": 1,
        "do_not_include_in_total": 1,
        "amount_based_on_formula": 1,
        "formula": "round(gross_pay * 0.0325) if gross_pay <= 21000 else 0",
        "round_to_the_nearest_integer": 1,
    },
    {
        "name": "PF Employer Contribution",
        "type": "Earning",
        "statistical_component": 1,
        "do_not_include_in_total": 1,
        "amount_based_on_formula": 1,
        "formula": "round(min(base, 15000) * 0.12)",
        "round_to_the_nearest_integer": 1,
    },
]
```

Wire into `before_migrate` so corrections survive future updates.

### Phase B — verify

Pick 3 employees across salary bands:
- Security guard at ₹13,000 base → expect ESI ₹98, PF ₹1,560
- Floor assistant at ₹15,000 base → expect ESI ₹113, PF ₹1,800
- Sales Executive at ₹30,000 base → expect ESI = 0 (above threshold), PF ₹1,800 (capped)

Generate a draft Salary Slip for each and confirm the math.

### Phase C — add to Salary Structures

Once the 5 canonical structures are designed (per `project_chundakadan_hr_payroll.md` rebuild plan), include ESI + PF + their employer counterparts where applicable.

### Phase D — delete the duplicate "Provident Fund" component

Verify no Salary Slips / Salary Structures reference it, then delete.

---

## Why "dynamically" matters

The current formulas hard-code thresholds (₹46K for ESI, ₹10K for PF). When the government revises ceilings (last revised 2017 for ESI; 2014 for PF wage cap), the formulas need a code change.

**Better pattern** — make ceilings configurable via Frappe System Settings or a Chundakadan Settings field:

```python
# Read from system config so HR can update without redeploying
esi_ceiling = frappe.db.get_single_value("Chundakadan Settings", "esi_wage_ceiling") or 21000
pf_ceiling = frappe.db.get_single_value("Chundakadan Settings", "pf_wage_ceiling") or 15000
```

This would mean adding 2 more Custom Fields on Chundakadan Settings + referencing them in the component formulas via `eval_globals` (Frappe lets you inject globals into formula evaluation context).

Defer this enhancement to v2 — for v1, hard-coded ₹21K / ₹15K is fine (matches today's law).
