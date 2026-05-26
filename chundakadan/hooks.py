app_name = "chundakadan"
app_title = "Chundakadan"
app_publisher = "Ashkar"
app_description = "chundakadan"
app_email = "muhammed786ashkar@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "chundakadan",
# 		"logo": "/assets/chundakadan/logo.png",
# 		"title": "Chundakadan",
# 		"route": "/chundakadan",
# 		"has_permission": "chundakadan.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/chundakadan/css/chundakadan.css"
# app_include_js = "/assets/chundakadan/js/item_selection_common.js"

# include js, css files in header of web template
# web_include_css = "/assets/chundakadan/css/chundakadan.css"
# web_include_js = "/assets/chundakadan/js/chundakadan.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "chundakadan/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Sales Order" : "public/js/sales_order.js",
    "Payment Entry" : "public/js/payment_entry.js",
    "Item" : "public/js/item.js",
    "Sales Invoice" : "public/js/sales_invoice.js",
    "Delivery Note" : "public/js/delivery_note.js",
    "Purchase Order" : "public/js/purchase_order.js",
    "Purchase Invoice" : "public/js/purchase_invoice.js",
    "Quotation" : "public/js/quotation.js",
    "Purchase Receipt" : "public/js/purchase_receipt.js",
    "Material Request" : "public/js/material_request.js",
    "Request for Quotation" : "public/js/request_for_quotation.js",
    "Supplier Quotation" : "public/js/supplier_quotation.js",
    "Leave Application" : "public/js/leave_application.js",
    "Exit Interview Form" : "public/js/exit_interview_form.js",
    "Interview" : "public/js/interview.js",
    "Period Salary Slip" : "public/js/period_salary_slip.js",
    "Employee" : "public/js/employee.js",
}
doctype_list_js = {
    "Leave Application" : "public/js/leave_application_list.js",
    "Employee Checkin" : "public/js/employee_checkin_list.js"
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "chundakadan/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "chundakadan.utils.jinja_methods",
# 	"filters": "chundakadan.utils.jinja_filters"
# }

# Installation
# ------------
doc_events = {
    "Payment Entry": {
        "validate":
        "chundakadan.doc_events.payment_entry.set_custom_sales_person",

        "before_save":
        "chundakadan.doc_events.payment_entry.set_custom_sales_person",
        "before_submit": [
            "chundakadan.doc_events.payment_entry.set_custom_sales_person",
            "chundakadan.doc_events.payment_entry.validate_check_bounce"
        ]
    },
    "Sales Order": {
        "validate": "chundakadan.doc_events.sales_order.validate_item_qty_in_stock"
    },
	"Sales Invoice": {
        "autoname": "chundakadan.doc_events.sales_invoice.autoname",
        "validate": "chundakadan.doc_events.sales_invoice.validate_sales_invoice",
        "on_trash": "chundakadan.doc_events.sales_invoice.on_trash"
    },
    "Leave Policy": {
        "before_save": "chundakadan.doc_events.leave_policy.set_annual_allocation_from_leave_type",
        "validate": "chundakadan.doc_events.leave_policy.validate_leave_policy_details"
    },
    "Leave Policy Assignment": {
        "before_submit": "chundakadan.doc_events.leave_policy_assignment.update_new_leaves_from_max_allowed"
    },
    "Leave Application": {
        "validate": "chundakadan.chundakadan.api.leave.validate_leave"
    },
    "Employee Checkin": {
        "after_insert": "chundakadan.doc_events.employee_checkin.mark_attendance",
        "on_update": "chundakadan.doc_events.employee_checkin.mark_attendance"
    }
}
# before_install = "chundakadan.install.before_install"
# after_install = "chundakadan.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "chundakadan.uninstall.before_uninstall"
# after_uninstall = "chundakadan.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "chundakadan.utils.before_app_install"
# after_app_install = "chundakadan.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "chundakadan.utils.before_app_uninstall"
# after_app_uninstall = "chundakadan.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "chundakadan.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
    "Leave Application": "chundakadan.chundakadan.api.leave.get_permission_query_conditions",
}

has_permission = {
    "Leave Application": "chundakadan.chundakadan.api.leave.has_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Leave Policy Assignment": "chundakadan.overrides.leave_policy_assignment.CustomLeavePolicyAssignment",
	"Leave Application":
    "chundakadan.overrides.leave_application.CustomLeaveApplication"
}


# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		"*/15 * * * *": [
			"chundakadan.chundakadan.doctype.crosschex_settings.crosschex_settings.scheduled_attendance_sync"
		],
		"0 */6 * * *": [
			"chundakadan.chundakadan.doctype.crosschex_settings.crosschex_settings.check_and_refresh_token"
		],
		# Daily at 01:00 — gates on Chundakadan Settings.annual_allocation_run_date,
		# fires the annual leave allocation only on the configured day.
		"0 1 * * *": [
			"chundakadan.chundakadan.api.leave.maybe_auto_allocate"
		]
	}
}

# Testing
# -------

# before_tests = "chundakadan.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "chundakadan.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "chundakadan.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["chundakadan.utils.before_request"]
# after_request = ["chundakadan.utils.after_request"]

# Job Events
# ----------
# before_job = ["chundakadan.utils.before_job"]
# after_job = ["chundakadan.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"chundakadan.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

fixtures = [
    {
        "doctype": "Report",
        "filters": [
            [
                "module",
                "=",
                "Chundakadan"
            ]
        ]
    },
    {
        "doctype": "Custom Field",
        "filters": [
            [
                "module",
                "in",
                "Chundakadan"
            ]
        ]
    },
    {
        "doctype": "Property Setter",
        "filters": [
            [
                "module",
                "in",
                "Chundakadan"
            ]
        ]
    },
    {
        "doctype": "Client Script",
        "filters": [
            [
                "module",
                "in",
                "Chundakadan"
            ]
        ]
    },
    {
        "doctype": "Document Naming Rule",
        "filters": [
            [
                "document_type",
                "in",
                [
                    "Performance Feedback Form",
                    "Management Feedback Form",
                    "Peer Feedback Form",
                    "Coordinator Feedback Form",
                    "Customer Feedback Form",
                    "Self Assessment Form",
                    "Period Salary Slip"
                ]
            ]
        ]
    },
    {
        "doctype": "Print Format",
        "filters": [
            [
                "module",
                "=",
                "Chundakadan"
            ]
        ]
    }

]
