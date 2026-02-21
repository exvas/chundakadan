# Year-End Leave Encashment Processing Guide

## Overview

At the end of each fiscal year, you can process leave encashment for all eligible employees. This guide explains the complete workflow for year-end leave encashment redemption.

## Year-End Encashment Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ FISCAL YEAR END                                             │
│ (e.g., March 31, 2026)                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Run Leave Encashment Balance Report                │
│ - Select Leave Period: FY 2025-26                          │
│ - Review all employees' pending encashment                  │
│ - Verify amounts and calculations                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Bulk Create Additional Salary                      │
│ - Click "Bulk Create Additional Salary"                    │
│ - Set Payroll Date: March 31, 2026 (year-end date)        │
│ - System creates entries for all eligible employees        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Review & Submit Additional Salary Entries          │
│ - Navigate to: HR > Additional Salary                      │
│ - Filter by Payroll Date: March 31, 2026                   │
│ - Review each entry                                        │
│ - Submit all entries                                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Process Payroll for March 2026                     │
│ - Create Salary Slips for March 2026                       │
│ - Leave Encashment automatically included                  │
│ - Process payments                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 5: Update Leave Records (Optional)                    │
│ - Update Leave Allocation "Total Leaves Encashed"          │
│ - Or create Leave Ledger Entries to reduce balance         │
│ - Maintain audit trail                                     │
└─────────────────────────────────────────────────────────────┘
```

## Detailed Step-by-Step Process

### Step 1: Run Year-End Report

**When:** Last week of fiscal year (e.g., March 25-31)

**Navigate to:** HR > Reports > Leave Encashment Balance

**Set Filters:**
```
✓ Leave Period: FY 2025-26 (or your fiscal year)
✓ Salary Component: Leave Encashment
□ Company: [Optional - if multi-company]
□ Department: [Optional - process all or by department]
□ Employee: [Leave blank for all employees]
□ Leave Type: [Leave blank for all encashable types]
✓ Payment Days: 30 (or as per company policy)
```

**Click:** Refresh

**Review:**
- Total employees eligible
- Total pending leaves
- Total payable amount
- Individual employee details

**Export (Optional):**
- Export to Excel for records
- Share with management for approval
- Keep for audit trail

### Step 2: Get Management Approval

**Prepare Summary:**
```
Year-End Leave Encashment Summary
Fiscal Year: 2025-26
Total Employees: 150
Total Leaves to Encash: 1,500 days
Total Amount: ₹7,50,000
Payroll Date: March 31, 2026
```

**Get Approvals:**
- HR Manager approval
- Finance Manager approval
- Management approval (if required)

### Step 3: Bulk Create Additional Salary

**Click:** "Bulk Create Additional Salary" button

**Review Summary:**
- Verify employee count
- Verify total amount
- Confirm salary component

**Click:** Yes to proceed

**Set Payroll Date:**
```
Payroll Date: March 31, 2026 (last day of fiscal year)
☑ Overwrite Salary Structure Amount
```

**Click:** Create All

**Review Results:**
- Successfully Created: X entries
- Skipped: Y entries (already processed)
- Failed: Z entries (check errors)

**If Failures:**
- Review error messages
- Fix issues (missing salary structure, etc.)
- Re-run for failed employees only

### Step 4: Review Additional Salary Entries

**Navigate to:** HR > Additional Salary

**Filter:**
```
Payroll Date: March 31, 2026
Status: Draft
```

**Review Each Entry:**
- Employee name and ID
- Salary component: Leave Encashment
- Amount (verify calculation)
- Remarks (shows leave type and days)

**Spot Check:**
- Pick 5-10 random entries
- Verify calculations manually
- Confirm with employee records

**Submit All:**
- Use bulk actions if available
- Or submit individually
- Ensure all are submitted before payroll

### Step 5: Process March Payroll

**Navigate to:** HR > Payroll Entry > New

**Or:** Create individual Salary Slips

**Settings:**
```
Payroll Period: March 2026
Start Date: March 1, 2026
End Date: March 31, 2026
```

**Create Salary Slips:**
- System automatically includes Additional Salary
- Leave Encashment appears in Earnings
- Verify amounts in sample slips

**Example Salary Slip:**
```
EARNINGS:
├─ Basic Salary:        ₹30,000
├─ HRA:                 ₹10,000
├─ Other Allowances:    ₹5,000
├─ Leave Encashment:    ₹5,000  ← Automatically added!
└─ Total Earnings:      ₹50,000

DEDUCTIONS:
└─ ...

NET PAY: ₹45,000 (example)
```

**Submit & Process:**
- Submit all salary slips
- Create Payroll Entry
- Process bank payments
- Generate payslips for employees

### Step 6: Update Leave Records

**Option A: Update Leave Allocation**

For each employee:
1. Open Leave Allocation
2. Update "Total Leaves Encashed" field
3. Add encashed leaves to existing count
4. Save

**Option B: Create Leave Ledger Entry**

This reduces the leave balance:
1. Navigate to: HR > Leave Ledger Entry > New
2. Employee: [Select]
3. Leave Type: [Select]
4. Transaction Type: Leave Encashment
5. Leaves: [Negative value, e.g., -15]
6. Transaction Date: March 31, 2026
7. Save and Submit

**Option C: Automated (Custom Script)**

Create a custom script to automatically update leave records when Additional Salary is submitted.

### Step 7: Year-End Closing

**Generate Reports:**
- Leave Encashment Summary Report
- Total amount paid per department
- Employee-wise encashment details

**Archive Documents:**
- Export report to PDF
- Save Additional Salary list
- Keep salary slips
- Maintain for audit

**Accounting Entries:**
- Verify journal entries created
- Check expense accounts
- Reconcile with payroll
- Close fiscal year books

## Best Practices

### Timing

✅ **Do:**
- Start review 2 weeks before year-end
- Get approvals 1 week before
- Process in last week of fiscal year
- Complete before year-end closing

❌ **Don't:**
- Wait until last day
- Process without approvals
- Skip verification steps
- Forget to update leave records

### Communication

**To Employees:**
```
Subject: Year-End Leave Encashment - FY 2025-26

Dear Team,

We are processing year-end leave encashment for eligible employees.

Your Details:
- Leave Type: Annual Leave
- Leaves Encashed: 15 days
- Amount: ₹5,000
- Payment Date: March 31, 2026

This amount will be included in your March salary.

For questions, contact HR.

Best regards,
HR Team
```

### Verification Checklist

Before processing:
- [ ] All leave allocations are submitted
- [ ] All employees have salary structure assignments
- [ ] Leave balances are accurate
- [ ] Encashment policy is correctly configured
- [ ] Management approval obtained
- [ ] Finance team notified

After processing:
- [ ] All Additional Salary entries created
- [ ] All entries submitted
- [ ] Salary slips include encashment
- [ ] Payments processed
- [ ] Leave records updated
- [ ] Reports generated and archived

## Handling Special Cases

### Case 1: Employee Resigned Mid-Year

**Scenario:** Employee resigned in January, but has pending encashment

**Solution:**
1. Calculate pro-rata encashment
2. Process with final settlement
3. Use resignation date as payroll date
4. Include in final salary slip

### Case 2: Employee on Long Leave

**Scenario:** Employee on maternity/medical leave

**Solution:**
1. Include in year-end processing
2. Process normally
3. Pay with regular salary when they return
4. Or process separately if needed

### Case 3: New Joinee

**Scenario:** Employee joined mid-year

**Solution:**
1. Pro-rata leave allocation
2. Calculate encashment on available balance
3. Process normally if eligible
4. Follow company policy on minimum tenure

### Case 4: Partial Encashment

**Scenario:** Employee wants to carry forward some leaves

**Solution:**
1. Check leave type settings
2. If carry forward allowed, adjust calculation
3. Encash only excess leaves
4. Update leave allocation accordingly

## Policy Considerations

### Maximum Encashable Leaves

Set in Leave Type:
```
Max Encashable Leaves: 30 days per year
```

This limits encashment even if balance is higher.

### Minimum Balance to Maintain

Set in Leave Type:
```
Non-Encashable Leaves: 5 days
```

Employee must maintain minimum balance.

### Encashment Frequency

Options:
- **Annual:** Once per fiscal year (recommended)
- **Quarterly:** Every 3 months
- **On-demand:** When employee requests
- **On exit:** During final settlement

### Tax Implications

**Important:** Leave encashment may be taxable

- Configure salary component as taxable
- System calculates tax automatically
- Consult with tax advisor
- Follow local tax laws

## Troubleshooting

### Issue: Some employees not showing in report

**Check:**
1. Leave allocation exists and is submitted
2. Leave type has encashment enabled
3. Employee has leave balance > non-encashable
4. Salary structure assignment exists
5. Correct leave period selected

### Issue: Amount calculation seems wrong

**Verify:**
1. Basic salary in salary structure
2. Payment days setting (default: 30)
3. Pending leaves calculation
4. Per day rate = Basic ÷ Payment Days

### Issue: Additional Salary not in Salary Slip

**Ensure:**
1. Additional Salary is submitted (not draft)
2. Payroll date falls within salary slip period
3. Employee matches
4. Salary component exists

### Issue: Bulk creation failed for some employees

**Review:**
1. Error messages in results dialog
2. Check Error Log in ERPNext
3. Fix issues (missing data, etc.)
4. Re-run for failed employees

## Example: Complete Year-End Process

**Company:** ABC Ltd  
**Fiscal Year:** April 2025 - March 2026  
**Employees:** 100  
**Processing Date:** March 25, 2026

**Day 1 (March 25):**
- Run report
- Export to Excel
- Review with HR Manager
- Identify 85 eligible employees
- Total amount: ₹4,25,000

**Day 2 (March 26):**
- Present to Finance Manager
- Get approval
- Prepare communication to employees

**Day 3 (March 27):**
- Bulk create Additional Salary
- Set payroll date: March 31, 2026
- 85 entries created successfully
- Review and spot-check 10 entries

**Day 4 (March 28):**
- Submit all Additional Salary entries
- Send communication to employees
- Notify Finance team

**Day 5 (March 29):**
- Create Salary Slips for March
- Verify encashment included
- Submit salary slips

**Day 6 (March 30):**
- Process Payroll Entry
- Generate bank file
- Submit for payment processing

**Day 7 (March 31):**
- Payments processed
- Update leave records
- Generate final reports
- Archive documents

**Post Year-End:**
- Verify accounting entries
- Close fiscal year
- Prepare for next year

## Summary

The Leave Encashment Balance Report is designed for year-end processing:

✅ **View:** See all pending encashments at year-end  
✅ **Redeem:** Bulk create Additional Salary for all employees  
✅ **Process:** Include in final month's payroll  
✅ **Track:** Maintain complete audit trail  
✅ **Report:** Generate summaries for management  

The system handles the complete workflow from calculation to payment, making year-end leave encashment processing efficient and accurate.
