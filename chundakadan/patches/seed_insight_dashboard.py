"""Seed the executive 'Insight' dashboard — company-wide KPI number cards and
charts. Idempotent; run on migrate. Workspace ships as a module file.

Dynamic-date filters use JS expressions (evaluated client-side by
dashboard_utils.js), NOT Python — e.g. frappe.datetime.month_start().
"""
import json
import frappe

MODULE = "Chundakadan"

# label, document_type, function, agg_field, filters, dynamic_filters, color
CARDS = [
    ("Sales This Month", "Sales Invoice", "Sum", "base_grand_total",
     [["Sales Invoice", "docstatus", "=", 1]],
     [["Sales Invoice", "posting_date", ">=", "frappe.datetime.month_start()"],
      ["Sales Invoice", "posting_date", "<=", "frappe.datetime.month_end()"]], "green"),
    ("Sales This Year", "Sales Invoice", "Sum", "base_grand_total",
     [["Sales Invoice", "docstatus", "=", 1]],
     [["Sales Invoice", "posting_date", ">=", "frappe.datetime.year_start()"],
      ["Sales Invoice", "posting_date", "<=", "frappe.datetime.year_end()"]], "blue"),
    ("Purchases This Month", "Purchase Invoice", "Sum", "base_grand_total",
     [["Purchase Invoice", "docstatus", "=", 1]],
     [["Purchase Invoice", "posting_date", ">=", "frappe.datetime.month_start()"],
      ["Purchase Invoice", "posting_date", "<=", "frappe.datetime.month_end()"]], "orange"),
    ("Receivables Outstanding", "Sales Invoice", "Sum", "outstanding_amount",
     [["Sales Invoice", "docstatus", "=", 1], ["Sales Invoice", "outstanding_amount", ">", 0]],
     None, "red"),
    ("Payables Outstanding", "Purchase Invoice", "Sum", "outstanding_amount",
     [["Purchase Invoice", "docstatus", "=", 1], ["Purchase Invoice", "outstanding_amount", ">", 0]],
     None, "orange"),
    ("Sales Orders This Month", "Sales Order", "Count", None,
     [["Sales Order", "docstatus", "=", 1]],
     [["Sales Order", "transaction_date", ">=", "frappe.datetime.month_start()"],
      ["Sales Order", "transaction_date", "<=", "frappe.datetime.month_end()"]], "blue"),
    ("Active Employees", "Employee", "Count", None,
     [["Employee", "status", "=", "Active"]], None, "purple"),
    ("Pending Leave Approvals", "Leave Application", "Count", None,
     [["Leave Application", "custom_approval_status", "=", "Pending"]], None, "yellow"),
]

# chart_name, doctype, spec
CHARTS = [
    ("Monthly Sales Trend", "Sales Invoice", {
        "chart_type": "Sum", "based_on": "posting_date", "value_based_on": "base_grand_total",
        "timeseries": 1, "time_interval": "Monthly", "type": "Line",
        "filters_json": json.dumps([["Sales Invoice", "docstatus", "=", 1]])}),
    ("Monthly Collections", "Payment Entry", {
        "chart_type": "Sum", "based_on": "posting_date", "value_based_on": "base_received_amount",
        "timeseries": 1, "time_interval": "Monthly", "type": "Bar",
        "filters_json": json.dumps([["Payment Entry", "docstatus", "=", 1],
                                    ["Payment Entry", "payment_type", "=", "Receive"]])}),
    ("Monthly Purchases", "Purchase Invoice", {
        "chart_type": "Sum", "based_on": "posting_date", "value_based_on": "base_grand_total",
        "timeseries": 1, "time_interval": "Monthly", "type": "Line",
        "filters_json": json.dumps([["Purchase Invoice", "docstatus", "=", 1]])}),
    ("Top Customers by Sales", "Sales Invoice", {
        "chart_type": "Group By", "group_by_type": "Sum", "group_by_based_on": "customer",
        "aggregate_function_based_on": "base_grand_total", "number_of_groups": 10, "type": "Bar",
        "filters_json": json.dumps([["Sales Invoice", "docstatus", "=", 1]])}),
]


def execute():
    for label, dt, func, agg, filters, dynamic, color in CARDS:
        doc = {
            "doctype": "Number Card", "label": label, "type": "Document Type",
            "document_type": dt, "function": func,
            "filters_json": json.dumps(filters),
            "dynamic_filters_json": json.dumps(dynamic) if dynamic else None,
            "color": color, "is_public": 1, "module": MODULE,
        }
        if agg:
            doc["aggregate_function_based_on"] = agg
        if frappe.db.exists("Number Card", label):
            existing = frappe.get_doc("Number Card", label)
            existing.update(doc)
            existing.save(ignore_permissions=True)
        else:
            frappe.get_doc(doc).insert(ignore_permissions=True)

    for name, dt, spec in CHARTS:
        base = {"doctype": "Dashboard Chart", "chart_name": name, "document_type": dt,
                "is_public": 1, "module": MODULE}
        base.update(spec)
        if frappe.db.exists("Dashboard Chart", name):
            d = frappe.get_doc("Dashboard Chart", name)
            d.update(base)
            d.save(ignore_permissions=True)
        else:
            frappe.get_doc(base).insert(ignore_permissions=True)
