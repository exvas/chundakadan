from chundakadan.dispatch.events import backfill_dispatch_logs
from chundakadan.dispatch.setup import ensure_dispatch_role, ensure_sales_invoice_field


def execute():
	# Patches run before after_migrate, so make sure the role and the Sales
	# Invoice field exist before logs mirror their status onto invoices.
	ensure_dispatch_role()
	ensure_sales_invoice_field()
	backfill_dispatch_logs()
