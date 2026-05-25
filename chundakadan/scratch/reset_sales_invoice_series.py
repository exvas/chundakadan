import frappe

def execute():
    # The actual series prefix stored in the database for 2026
    series_prefixes = ["SI-26-", "SR-26-"]
    
    for prefix in series_prefixes:
        # Check if the series exists in tabSeries
        exists = frappe.db.sql("SELECT name, current FROM tabSeries WHERE name = %s", prefix)
        
        if exists:
            # Update the sequence counter back to 0
            frappe.db.sql("UPDATE tabSeries SET current = 0 WHERE name = %s", prefix)
            print(f"Successfully reset the sequence for {prefix} back to 0.")
        else:
            print(f"Series {prefix} not found in tabSeries (it might already be at 0 or never created).")
            
    frappe.db.commit()
    print("Series reset complete.")
