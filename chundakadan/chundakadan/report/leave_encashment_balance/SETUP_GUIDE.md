# Leave Encashment Setup Guide

## Step-by-Step Setup

### 1. Create Leave Encashment Salary Component

Navigate to: **HR > Salary Component > New**

Create a new Salary Component with these settings:

```
Salary Component Name: Leave Encashment
Type: Earning
Is Taxable: Yes (or as per your tax rules)
Is Flexible Benefit: No
Depends on Payment Days: No
Statistical Component: No
Do Not Include in Total: No
```

**Save** the Salary Component.

### 2. Configure Leave Types for Encashment

Navigate to: **HR > Leave Type > [Select Leave Type]**

For each leave type you want to enable encashment:

```
☑ Allow Encashment
Max Encashable Leaves: [e.g., 30] (optional - leave blank for unlimited)
Non Encashable Leaves: [e.g., 5] (optional - minimum balance to maintain)
```

**Example:**
- Annual Leave: Allow Encashment ✓, Max: 30, Non-Encashable: 5
- Sick Leave: Allow Encashment ✗ (not encashable)

### 3. Ensure Salary Structure Assignments

Navigate to: **HR > Salary Structure Assignment**

Verify that all employees have:
- Active Salary Structure Assignment
- Base salary amount filled
- Assignment is submitted (docstatus = 1)

### 4. Create Leave Period

Navigate to: **HR > Leave Period > New**

```
Leave Period Name: 2026
From Date: 2026-01-01
To Date: 2026-12-31
Company: [Your Company]
```

**Save and Submit** the Leave Period.

### 5. Allocate Leaves

Navigate to: **HR > Leave Allocation > New**

For each employee and leave type:

```
Employee: [Select Employee]
Leave Type: [Select Encashment-enabled Leave Type]
From Date: 2026-01-01
To Date: 2026-12-31
Leave Period: 2026
New Leaves Allocated: [e.g., 30]
```

**Save and Submit** the Leave Allocation.

## Using the Report

### Step 1: Open the Report

Navigate to: **HR > Reports > Leave Encashment Balance**

### Step 2: Set Filters

```
Company: [Your Company] (optional)
Leave Period: 2026 (required)
Department: [Filter by department] (optional)
Employee: [Filter by employee] (optional)
Leave Type: [Filter by leave type] (optional)
Payment Days: 30 (required - adjust as needed)
Leave Encashment Salary Component: Leave Encashment (required for creating Additional Salary)
```

### Step 3: Review Report

The report will show:
- Employees with encashment-enabled leave types
- Current leave balances
- Pending leaves available for encashment
- Calculated payable amounts

### Step 4: Create Additional Salary

**Option 1: Individual Creation**

For each employee you want to process:

1. Click the **"Create"** button in the Action column
2. Review the confirmation dialog showing:
   - Employee name
   - Leave type
   - Number of leaves
   - Payable amount
3. Click **Yes** to proceed
4. Enter the **Payroll Date** (e.g., 2026-02-28)
5. Check/uncheck **Overwrite Salary Structure Amount** (default: checked)
6. Click **Create**

**Option 2: Bulk Creation (Recommended for multiple employees)**

To create Additional Salary for all eligible employees at once:

1. Click the **"Bulk Create Additional Salary"** button at the top of the report
2. Review the summary showing:
   - Total employees
   - Total leaves
   - Total amount
   - Salary component
3. Click **Yes** to proceed
4. Enter the **Payroll Date** (e.g., 2026-02-28) - same for all employees
5. Check/uncheck **Overwrite Salary Structure Amount** (default: checked)
6. Click **Create All**
7. Review the results:
   - Successfully created
   - Skipped (already exists)
   - Failed (with error messages)

The system will:
- Create Additional Salary entries for all eligible employees
- Skip employees who already have entries for the same date
- Show detailed results with success/failure counts
- Provide error messages for any failures

### Step 5: Review and Submit Additional Salary

1. Click the link in the success message to open the Additional Salary
2. Review all details
3. Make any adjustments if needed
4. Click **Submit** to finalize

### Step 6: Process Payroll

When creating Salary Slips:

1. Navigate to: **HR > Salary Slip > New** or use **Payroll Entry**
2. Select the employee and payroll period
3. The Additional Salary will automatically be included if:
   - The payroll date falls within the Salary Slip period
   - The Additional Salary is submitted
4. The Leave Encashment component will appear under Earnings
5. Process the Salary Slip as usual

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Setup                                                     │
│    - Create Salary Component (Leave Encashment)             │
│    - Enable Encashment on Leave Types                       │
│    - Assign Salary Structures to Employees                  │
│    - Create Leave Period                                    │
│    - Allocate Leaves                                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Run Report                                               │
│    - Select Leave Period                                    │
│    - Select Salary Component                                │
│    - Apply filters as needed                                │
│    - Review pending encashments                             │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Create Additional Salary                                 │
│    - Click button for each employee                         │
│    - Select payroll date                                    │
│    - System creates Additional Salary entry                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Review & Submit                                          │
│    - Open Additional Salary document                        │
│    - Verify details                                         │
│    - Submit the document                                    │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Process Payroll                                          │
│    - Create Salary Slip for the period                      │
│    - Additional Salary auto-included                        │
│    - Leave Encashment appears in Earnings                   │
│    - Process payment                                        │
└─────────────────────────────────────────────────────────────┘
```

## Troubleshooting

### Issue: No data in report

**Solution:**
- Verify Leave Period is selected
- Check that leave types have "Allow Encashment" enabled
- Ensure employees have leave allocations for the period
- Confirm leave allocations are submitted

### Issue: "Create Additional Salary" button not working

**Solution:**
- Ensure "Leave Encashment Salary Component" filter is set
- Verify the employee has pending encashment leaves (> 0)
- Check that you have permission to create Additional Salary

### Issue: Additional Salary not appearing in Salary Slip

**Solution:**
- Verify Additional Salary is submitted (not draft)
- Check that payroll date falls within Salary Slip period
- Ensure employee matches
- Confirm salary component exists in the system

### Issue: Amount is zero or incorrect

**Solution:**
- Verify employee has active Salary Structure Assignment
- Check that base salary is filled in the assignment
- Confirm payment days is set correctly (default: 30)
- Review leave balance calculation

## Best Practices

1. **Regular Processing**: Run the report monthly or quarterly to process encashments
2. **Batch Processing**: Use filters to process by department for better control
3. **Verification**: Always review Additional Salary entries before submitting
4. **Documentation**: The system automatically adds remarks with calculation details
5. **Audit Trail**: Keep track of encashments through the Additional Salary records
6. **Year-End**: Process all pending encashments before closing the financial year
7. **Policy Compliance**: Ensure max encashable and non-encashable limits match company policy

## FAQs

**Q: Can I encash leaves multiple times in a period?**
A: Yes, but the system checks for duplicates on the same payroll date to prevent double-payment.

**Q: What happens to the leave balance after encashment?**
A: The leave balance remains unchanged. You need to manually adjust the Leave Allocation's "Total Leaves Encashed" field or create a Leave Ledger Entry to reduce the balance.

**Q: Can I modify the amount before submitting?**
A: Yes, the Additional Salary is created in draft state. You can edit any field before submitting.

**Q: Is the encashment amount taxable?**
A: This depends on your Salary Component configuration. Set "Is Taxable" accordingly.

**Q: Can I cancel an Additional Salary after it's included in a Salary Slip?**
A: No, you cannot cancel an Additional Salary that's already included in a submitted Salary Slip. You would need to cancel the Salary Slip first.

## Support

For issues or questions:
1. Check ERPNext HRMS documentation
2. Review this guide and README.md
3. Contact your system administrator
4. Raise an issue in the project repository
