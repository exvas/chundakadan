import frappe
from frappe import _

@frappe.whitelist()
def get_sales_order_list():
    return frappe.get_all(
        'Sales Order',
        filters={'docstatus': 1},
        fields=['name'],
        order_by='creation desc',
        limit_page_length=100
    )

@frappe.whitelist()
def get_so_details(filters=None):
    import json
    if isinstance(filters, str):
        filters = json.loads(filters)
    filters = filters or {}

    so_filters = {'docstatus': 1}
    if filters.get("sales_order"):
        so_filters["name"] = filters['sales_order']
    if filters.get("from_date") and filters.get("to_date"):
        so_filters["transaction_date"] = ["between", [filters["from_date"], filters["to_date"]]]
    elif filters.get("from_date"):
        so_filters["transaction_date"] = [">=", filters["from_date"]]
    elif filters.get("to_date"):
        so_filters["transaction_date"] = ["<=", filters["to_date"]]

    data = []
    sales_orders = frappe.get_all(
        'Sales Order',
        filters=so_filters,
        fields=['name', 'customer', 'transaction_date', 'status']
    )
    for so in sales_orders:
        so_items = frappe.get_all('Sales Order Item',
            filters={'parent': so.name},
            fields=['name', 'item_code', 'qty', 'warehouse']
        )
        if so_items:
            so_item_names = [item['name'] for item in so_items]
        else:
            so_item_names = []

        invoiced_qty_map = {}
        if so_item_names:
            invoice_rows = frappe.db.sql("""
                SELECT soi.name AS so_item, 
                    IFNULL(SUM(sii.qty), 0) AS billed_qty
                FROM `tabSales Invoice Item` sii
                JOIN `tabSales Order Item` soi ON sii.so_detail = soi.name
                WHERE soi.name IN %(so_item_names)s
                    AND sii.docstatus = 1
                GROUP BY soi.name
            """, {"so_item_names": tuple(so_item_names)}, as_dict=1)
            invoiced_qty_map = {row.so_item: row.billed_qty for row in invoice_rows}

        for item in so_items:
            stock_qty = get_stock_qty(item.item_code, item.warehouse)
            billed_qty = float(invoiced_qty_map.get(item.name, 0))
            qty_to_invoice = float(item.qty) - billed_qty
            remaining_qty = float(stock_qty) - float(item.qty)
            # Only include if qty_to_invoice > 0
            if qty_to_invoice > 0:
                item_data = {
                    'sales_order': so.name,
                    'customer': so.customer,
                    'date': so.transaction_date,
                    'status': so.status,
                    'item_code': item.item_code,
                    'ordered_qty': item.qty,
                    'warehouse': item.warehouse,
                    'stock_qty': stock_qty,
                    'remaining_qty': remaining_qty,
                    'qty_to_invoice': qty_to_invoice,
                }
                data.append(item_data)
    return data

def get_stock_qty(item_code, warehouse):
    bin_data = frappe.db.get_value(
        'Bin',
        {'item_code': item_code, 'warehouse': warehouse},
        ['actual_qty'],
        as_dict=1
    )
    return float(bin_data.actual_qty) if bin_data and bin_data.actual_qty else 0.0
