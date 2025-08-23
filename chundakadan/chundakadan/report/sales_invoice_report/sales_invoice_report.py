# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data


def get_columns(filters):
    """Define the columns for the report"""
    columns = [
        {
            "label": _("Item Code"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 150
        },
        {
            "label": _("Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Item Group"),
            "fieldname": "item_group",
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 120
        },
        {
            "label": _("UOM"),
            "fieldname": "stock_uom",
            "fieldtype": "Link",
            "options": "UOM",
            "width": 80
        },
        {
            "label": _("Valuation Rate"),
            "fieldname": "valuation_rate",
            "fieldtype": "Currency",
            "width": 120
        }
    ]
    
    # Get all active price lists
    price_lists = frappe.get_all(
        "Price List",
        filters={"enabled": 1, "selling": 1},
        fields=["name"],
        order_by="name"
    )
    
    # Add dynamic columns for each price list
    for price_list in price_lists:
        columns.append({
            "label": _(price_list.name),
            "fieldname": price_list.name.lower().replace(" ", "_"),
            "fieldtype": "Currency",
            "width": 120
        })
    
    return columns


def get_data(filters):
    """Fetch data for the report"""
    conditions = get_conditions(filters)
    
    # Get all items based on filters with UOM
    item_query = f"""
        SELECT 
            item_code,
            item_name,
            item_group,
            stock_uom
        FROM `tabItem`
        WHERE disabled = 0 {conditions}
        ORDER BY item_code
    """
    
    items = frappe.db.sql(item_query, filters, as_dict=True)
    
    # Get all active selling price lists
    price_lists = frappe.get_all(
        "Price List",
        filters={"enabled": 1, "selling": 1},
        fields=["name"],
        order_by="name"
    )
    
    # Get all item prices for these price lists
    if items and price_lists:
        item_codes = [item.item_code for item in items]
        price_list_names = [pl.name for pl in price_lists]
        
        # Create placeholders for the query
        item_placeholders = ', '.join(['%s'] * len(item_codes))
        price_list_placeholders = ', '.join(['%s'] * len(price_list_names))
        
        price_query = f"""
            SELECT 
                item_code,
                price_list,
                price_list_rate
            FROM `tabItem Price`
            WHERE item_code IN ({item_placeholders}) 
            AND price_list IN ({price_list_placeholders})
            AND selling = 1
        """
        
        prices = frappe.db.sql(
            price_query, 
            item_codes + price_list_names, 
            as_dict=True
        )
        
        # Create a price mapping
        price_map = {}
        for price in prices:
            key = f"{price.item_code}_{price.price_list}"
            price_map[key] = price.price_list_rate
    else:
        price_map = {}
    
    # Get valuation rates from Bin
    valuation_rates = {}
    if items:
        # Get warehouse filter if provided
        warehouse_condition = ""
        if filters.get("warehouse"):
            warehouse_condition = " AND warehouse = %(warehouse)s"
        
        item_placeholders = ', '.join(['%s'] * len(item_codes))
        
        valuation_query = f"""
            SELECT 
                item_code,
                valuation_rate,
                warehouse
            FROM `tabBin`
            WHERE item_code IN ({item_placeholders}) {warehouse_condition}
        """
        
        valuation_data = frappe.db.sql(
            valuation_query, 
            item_codes + ([filters.get("warehouse")] if filters.get("warehouse") else []), 
            as_dict=True
        )
        
        # Create valuation rate mapping - use average if multiple warehouses
        for val_data in valuation_data:
            item_code = val_data.item_code
            if item_code not in valuation_rates:
                valuation_rates[item_code] = []
            if val_data.valuation_rate:
                valuation_rates[item_code].append(val_data.valuation_rate)
        
        # Calculate average valuation rate per item
        for item_code in valuation_rates:
            if valuation_rates[item_code]:
                valuation_rates[item_code] = sum(valuation_rates[item_code]) / len(valuation_rates[item_code])
            else:
                valuation_rates[item_code] = 0.0
    
    # Build the final data
    data = []
    for item in items:
        row = {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "item_group": item.item_group,
            "stock_uom": item.stock_uom,
            "valuation_rate": valuation_rates.get(item.item_code, 0.0)
        }
        
        # Add price data for each price list
        for price_list in price_lists:
            fieldname = price_list.name.lower().replace(" ", "_")
            key = f"{item.item_code}_{price_list.name}"
            row[fieldname] = price_map.get(key, 0.0)
        
        data.append(row)
    
    return data


def get_conditions(filters):
    """Build SQL conditions based on filters"""
    conditions = ""
    
    if filters.get("item_code"):
        conditions += " AND item_code = %(item_code)s"
    
    if filters.get("item_group"):
        conditions += " AND item_group = %(item_group)s"
    
    if filters.get("item_name"):
        conditions += " AND item_name LIKE %(item_name)s"
        filters["item_name"] = f"%{filters['item_name']}%"
    
    if filters.get("stock_uom"):
        conditions += " AND stock_uom = %(stock_uom)s"
    
    return conditions


# Alternative version with chart support
def get_chart_data(data, filters):
    """Optional: Generate chart data"""
    if not data:
        return None
    
    # Get price list names for chart
    price_lists = frappe.get_all(
        "Price List",
        filters={"enabled": 1, "selling": 1},
        fields=["name"],
        order_by="name"
    )
    
    chart = {
        "data": {
            "labels": [row["item_code"] for row in data[:10]],  # Limit to first 10 items
            "datasets": []
        },
        "type": "bar",
        "height": 300
    }
    
    # Add dataset for each price list
    for price_list in price_lists:
        fieldname = price_list.name.lower().replace(" ", "_")
        dataset = {
            "name": price_list.name,
            "values": [row.get(fieldname, 0) for row in data[:10]]
        }
        chart["data"]["datasets"].append(dataset)
    
    return chart