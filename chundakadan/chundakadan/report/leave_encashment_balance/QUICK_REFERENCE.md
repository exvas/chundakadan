# Leave Encashment - Quick Reference Card

## 🎯 Your Question Answered

**Q: When I do salary slip with the payroll date, will it add this salary component with the leave encashed money?**

**A: YES! ✅**

When you:
1. Create Additional Salary with payroll date = Feb 28, 2026
2. Submit the Additional Salary
3. Create Salary Slip for February 2026

→ ERPNext **automatically** adds the Leave Encashment component with the amount to the Salary Slip!

**No manual work needed!** 🎉

---

## ⚡ Quick Usage

### 1. One-Time Setup (5 minutes)

```
1. Create Salary Component: "Leave Encashment" (Type: Earning)
2. Enable encashment on Leave Types
3. Ensure employees have Salary Structure Assignments
```

### 2. Run Report

```
HR > Reports > Leave Encashment Balance

Required Filters:
├─ Leave Period: [Select]
└─ Salary Component: Leave Encashment

Optional Filters:
├─ Company
├─ Department
├─ Employee
└─ Leave Type
```

### 3. Create Additional Salary

**Individual:**
```
1. Click "Create" button (in Action column for each employee)
2. Confirm details in dialog
3. Select Payroll Date (e.g., 2026-02-28)
4. Click "Create"
5. Review and Submit the Additional Salary
```

**Bulk (Recommended):**
```
1. Click "Bulk Create Additional Salary" button (at top of report)
2. Review summary (employees, leaves, amount)
3. Select Payroll Date (same for all)
4. Click "Create All"
5. Review results (created/skipped/failed)
6. Submit all Additional Salary entries
```

### 4. Process Payroll

```
HR > Salary Slip > New

1. Select Employee
2. Select Period (e.g., Feb 2026)
3. Leave Encashment automatically appears in Earnings! ✅
4. Process as usual
```

---

## 📊 Report Columns Explained

| Column | What It Shows |
|--------|---------------|
| **Pending for Encashment** | Leaves you can encash now |
| **Total Payable Amount** | Money employee will receive |
| **Current Balance** | Total leaves available |
| **Leaves Already Encashed** | Previously encashed leaves |

---

## 💡 Key Formulas

```
Per Day Rate = Basic Salary ÷ Payment Days (default: 30)

Pending Leaves = min(
    Current Balance - Non-Encashable Leaves,
    Max Encashable Leaves
)

Total Payable = Pending Leaves × Per Day Rate
```

---

## 🔄 Complete Workflow

```
┌──────────────────────────────────────────────────────────┐
│ 1. Run Report                                            │
│    → See pending encashments                             │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│ 2. Bulk Create (or Individual)                           │
│    → Click "Bulk Create Additional Salary"               │
│    → Review summary                                      │
│    → Select payroll date                                 │
│    → All Additional Salaries created                     │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│ 3. Submit Additional Salaries                            │
│    → Review details                                      │
│    → Submit all entries                                  │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│ 4. Create Salary Slips                                   │
│    → Leave Encashment AUTO-ADDED! ✅                     │
│    → Process payments                                    │
└──────────────────────────────────────────────────────────┘
```

---

## ⚠️ Important Points

### ✅ DO:
- Select Salary Component filter before creating Additional Salary
- Submit Additional Salary before creating Salary Slip
- Verify payroll date falls within Salary Slip period
- Review Additional Salary details before submitting

### ❌ DON'T:
- Create Additional Salary without selecting Salary Component
- Leave Additional Salary in draft state
- Create duplicate entries for same employee and date
- Forget to submit Additional Salary

---

## 🎯 Example Scenario

```
Employee: John Doe (EMP-001)
Leave Type: Annual Leave
Current Balance: 25 days
Non-Encashable: 5 days
Max Encashable: 30 days
Basic Salary: ₹30,000
Payment Days: 30

Calculation:
├─ Encashable Balance = 25 - 5 = 20 days
├─ Pending Leaves = min(20, 30) = 20 days
├─ Per Day Rate = 30,000 ÷ 30 = ₹1,000
└─ Total Payable = 20 × 1,000 = ₹20,000

Action:
1. Click "Create Additional Salary"
2. Select Payroll Date: 2026-02-28
3. Additional Salary created with ₹20,000
4. Submit Additional Salary
5. Create Salary Slip for Feb 2026
6. Salary Slip shows:
   ├─ Basic: ₹30,000
   ├─ Leave Encashment: ₹20,000 ← Auto-added!
   └─ Total: ₹50,000 (+ other components)
```

---

## 🔍 Troubleshooting

| Problem | Solution |
|---------|----------|
| Button not showing | Select Salary Component filter |
| No data in report | Check Leave Period and encashment settings |
| Additional Salary not in Slip | Ensure it's submitted and date matches |
| Amount is zero | Verify Salary Structure Assignment exists |
| Bulk creation failed | Check error messages in results dialog |

---

## 📞 Need Help?

1. Check **README.md** for detailed documentation
2. Read **SETUP_GUIDE.md** for step-by-step setup
3. Review **FEATURE_SUMMARY.md** for technical details
4. Contact your system administrator

---

## ✨ Features at a Glance

✅ Encashment-enabled leave types only  
✅ Real-time balance calculation  
✅ Automatic amount calculation  
✅ One-click Additional Salary creation  
✅ Bulk creation for all employees  
✅ Auto-populate all fields  
✅ Duplicate prevention  
✅ Automatic Salary Slip inclusion  
✅ Summary cards and charts  
✅ Visual highlighting  
✅ Comprehensive validation  
✅ Detailed results reporting  

---

## 🎉 You're All Set!

The report is ready to use. Navigate to:

**HR > Reports > Leave Encashment Balance**

Happy encashing! 💰
