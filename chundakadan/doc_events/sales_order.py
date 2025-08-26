import frappe


@frappe.whitelist()
def validate_item_qty_in_stock(doc, method=None):
    for item in doc.items:
        if item.item_code and item.warehouse:
                available_qty=frappe.get_value("Bin",
                {"item_code":item.item_code,"warehouse":item.warehouse
                },"actual_qty")
                if available_qty<item.qty:
                        frappe.throw(
                        f"Item {item.item_code} in warehouse {item.warehouse}: "
                        f"Only {available_qty} available, but {item.qty} required.",
                        title="Insufficient Stock"
                    )
