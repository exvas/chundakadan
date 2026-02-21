# Leave Encashment Balance Report

## Overview
This report provides a comprehensive view of leave encashment balances for employees with encashment-enabled leave types.

## Features

✅ **Encashment-enabled leave types** - Only shows leave types where encashment is allowed  
✅ **Total eligible leaves** - Shows total leaves allocated to each employee  
✅ **Leaves already encashed** - Displays count of leaves that have been encashed  
✅ **Leaves taken** - Shows approved leaves taken during the period  
✅ **Current balance** - Real-time leave balance calculation  
✅ **Pending leaves for encashment** - Calculates leaves available for encashment  
✅ **Encashment amount calculation** - Based on Basic Salary ÷ Payment Days  
✅ **Total payable amount** - Shows total amount payable for pending encashment  
✅ **Create Additional Salary** - One-click button to create Additional Salary entries  
✅ **Bulk Create** - Create Additional Salary for all employees at once  
✅ **Auto-populate fields** - Automatically fills employee, amount, and remarks in Additional Salary  

## Create Additional Salary Button

### Individual Creation

Each employee row with pending encashment leaves has a "Create" button in the Action column that:

1. Opens a dialog to confirm the payroll date
2. Creates an Additional Salary entry with pre-filled details:
   - Employee and Employee Name
   - Salary Component (from filter)
   - Amount (calculated encashment amount)
   - Payroll Date (user-selected)
   - Remarks (includes leave type, leaves count, and per-day rate)
3. Links to the Leave Type for reference
4. Redirects to the created Additional Salary document

### Bulk Creation

A "Bulk Create Additional Salary" button at the top of the report allows you to:

1. Create Additional Salary entries for ALL eligible employees at once
2. Shows a summary before creation:
   - Total employees
   - Total leaves to encash
   - Total amount payable
3. Select a single payroll date for all entries
4. Displays detailed results:
   - Successfully created
   - Skipped (already exists)
   - Failed (with error messages)
5. Automatically skips employees who already have Additional Salary for the same date

### How to Use Bulk Creation:

1. **Run the report** with desired filters (Department, Leave Type, etc.)
2. **Select Salary Component** - Choose a Leave Encashment Salary Component in the filters (required)
3. **Click "Bulk Create Additional Salary"** - Button appears at the top of the report
4. **Review Summary** - Check total employees, leaves, and amount
5. **Select Payroll Date** - Choose the date for all entries
6. **Click "Create All"** - System creates all entries
7. **Review Results** - See how many were created, skipped, or failed

### Important Notes:

- The salary component filter must be set before creating Additional Salary (individual or bulk)
- The system checks for duplicate entries to prevent double-payment
- Additional Salary entries are created in draft state for review
- You can edit any Additional Salary before submitting
- Bulk creation is transactional - all successful entries are committed together  

## Report Columns

| Column | Description |
|--------|-------------|
| Employee | Employee ID (clickable link) |
| Employee Name | Full name of the employee |
| Department | Employee's department |
| Leave Type | Type of leave (only encashment-enabled) |
| Encashment Enabled | Checkbox indicator |
| Total Eligible Leaves | Total leaves allocated in the period |
| Leaves Already Encashed | Count of leaves already encashed |
| Leaves Taken | Approved leaves taken during the period |
| Current Balance | Current available leave balance |
| Pending for Encashment | Leaves available for encashment |
| Basic Salary | Employee's basic salary from salary structure |
| Payment Days | Number of days used for calculation (default: 30) |
| Per Day Rate | Basic Salary ÷ Payment Days |
| Total Payable Amount | Pending Leaves × Per Day Rate |

## Filters

1. **Company** (Optional) - Filter by company
2. **Leave Period** (Required) - Select the leave period for calculation
3. **Department** (Optional) - Filter by specific department
4. **Employee** (Optional) - View report for a specific employee
5. **Leave Type** (Optional) - Filter by specific encashment-enabled leave type
6. **Payment Days** (Required, Default: 30) - Number of days for per-day rate calculation
7. **Leave Encashment Salary Component** (Optional, Required for Additional Salary) - Salary component to use when creating Additional Salary entries

## Calculation Logic

### Pending Encashment Leaves
```
encashable_balance = max(0, current_balance - non_encashable_leaves)
pending_leaves = min(encashable_balance, max_encashable_leaves)
```

### Per Day Rate
```
per_day_rate = basic_salary / payment_days
```

### Total Payable Amount
```
total_payable = pending_leaves × per_day_rate
```

## Summary Cards

The report displays summary cards at the top:
- **Total Employees** - Count of employees in the report
- **Total Pending Leaves** - Sum of all pending encashment leaves
- **Total Encashed Leaves** - Sum of all already encashed leaves
- **Total Payable Amount** - Total amount payable across all employees

## Chart Visualization

The report includes a bar chart showing:
- Pending leaves for encashment (Orange)
- Already encashed leaves (Green)

Grouped by leave type for easy comparison.

## Prerequisites

1. **Leave Type Configuration**
   - Enable "Allow Encashment" in Leave Type
   - Set "Max Encashable Leaves" (optional)
   - Set "Non Encashable Leaves" (optional)

2. **Leave Allocation**
   - Employees must have leave allocations for the selected period
   - Leave allocations should be linked to a Leave Period

3. **Salary Structure Assignment**
   - Employees must have an active Salary Structure Assignment
   - The assignment must have a "Base" salary component

4. **Leave Applications**
   - Approved leave applications are counted in "Leaves Taken"

## Usage Example

1. Navigate to: **HR > Reports > Leave Encashment Balance**
2. Select a **Leave Period** (required)
3. Optionally filter by Company, Department, Employee, or Leave Type
4. Adjust **Payment Days** if needed (default is 30)
5. Click **Refresh** to generate the report

## Export Options

The report can be exported to:
- Excel
- CSV
- PDF (with letter head)

## Permissions

Access is granted to:
- HR Manager
- HR User
- System Manager

## Integration with Salary Slip

### How Additional Salary Works with Payroll:

When you create an Additional Salary entry from this report:

1. **Additional Salary Entry** is created with:
   - Employee details
   - Salary Component (Leave Encashment)
   - Amount (calculated encashment amount)
   - Payroll Date (the date you specify)

2. **Salary Slip Processing**:
   - When you create a Salary Slip for the employee
   - If the Salary Slip's payroll period includes the Additional Salary's payroll date
   - The Additional Salary component will be automatically added to the Salary Slip
   - The amount will appear under "Earnings" section

3. **Automatic Inclusion**:
   - ERPNext automatically fetches Additional Salary entries based on:
     - Employee match
     - Payroll date falls within the Salary Slip period
     - Additional Salary is submitted (docstatus = 1)
   - The salary component and amount are added to the Salary Slip

### Example Workflow:

```
1. Run Leave Encashment Balance Report
   └─> Employee has 10 pending leaves, ₹5,000 payable

2. Click "Create Additional Salary" button
   └─> Select Payroll Date: 2026-02-28
   └─> Additional Salary created with ₹5,000

3. Submit the Additional Salary entry

4. Create Salary Slip for February 2026
   └─> Salary Slip automatically includes:
       - Leave Encashment: ₹5,000 (from Additional Salary)
   └─> Total earnings increased by ₹5,000

5. Process Payroll Entry
   └─> Employee receives base salary + ₹5,000 encashment
```

### Important Points:

- **Payroll Date Matching**: The Additional Salary's payroll date must fall within the Salary Slip's start and end date
- **Submission Required**: Additional Salary must be submitted (not draft) to appear in Salary Slip
- **One-time Payment**: Once included in a Salary Slip, the Additional Salary is marked as paid
- **Overwrite Option**: "Overwrite Salary Structure Amount" checkbox allows the Additional Salary to override any default amount from the Salary Structure

### Answer to Your Question:

**Yes**, when you create a Salary Slip with a payroll date that matches the Additional Salary's payroll date, the leave encashment salary component will be automatically added to the Salary Slip with the calculated amount. You don't need to manually add it - ERPNext handles this automatically.

For example:
- If you set Payroll Date as February 28, 2026 in Additional Salary
- When you create a Salary Slip for February 2026 (or any period that includes Feb 28)
- The Leave Encashment component with the amount will automatically appear in the Salary Slip

## Notes

- The report only shows encashment-enabled leave types
- Basic salary is fetched from the latest active Salary Structure Assignment
- Leave balance is calculated as of the leave period end date
- The report includes a total row for numeric columns
- Pending encashment leaves and payable amounts are highlighted in the report
