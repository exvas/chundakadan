import frappe
from frappe import _

LOCATION_DOCTYPE = {
    "Warehouse": "Warehouse Rack",
    "Customer": "Customer", "Dealer": "Customer", "Retail Outlet": "Customer",
    "Service Center": "Display Service Center",
    "Supplier": "Supplier",
}

# to_location_type = None  -> leave the unit's location unchanged.
# allowed_from = None      -> allowed from any status.
TRANSITIONS = {
    "Receive at Warehouse": {"to_status": "In Warehouse", "to_location_type": "Warehouse",
        "allowed_from": {"At Supplier", "In Transit", "Under Repair"}, "requires": ["to_location"]},
    "Reserve": {"to_status": "Reserved", "to_location_type": "Warehouse",
        "allowed_from": {"In Warehouse", "Returned"}, "requires": []},
    "Dispatch": {"to_status": "In Transit", "to_location_type": None,
        "allowed_from": {"In Warehouse", "Reserved", "Returned"}, "requires": []},
    "Install at Customer": {"to_status": "Installed at Customer", "to_location_type": "Customer",
        "allowed_from": {"In Transit", "In Warehouse", "Reserved", "Returned"},
        "requires": ["customer", "expected_return_date"]},
    "Transfer": {"to_status": "Installed at Customer", "to_location_type": "Customer",
        "allowed_from": {"Installed at Customer"},
        "requires": ["customer", "expected_return_date"]},
    "Return to Warehouse": {"to_status": "Returned", "to_location_type": "Warehouse",
        "allowed_from": {"Installed at Customer", "In Transit", "Under Repair"}, "requires": ["to_location"]},
    "Send to Repair": {"to_status": "Under Repair", "to_location_type": "Service Center",
        "allowed_from": {"In Warehouse", "Returned", "Installed at Customer", "Damaged"},
        "requires": ["to_location"]},
    "Return from Repair": {"to_status": "In Warehouse", "to_location_type": "Warehouse",
        "allowed_from": {"Under Repair"}, "requires": ["to_location"]},
    "Mark Damaged": {"to_status": "Damaged", "to_location_type": None,
        "allowed_from": None, "requires": ["reason"]},
    "Mark Missing": {"to_status": "Missing", "to_location_type": None,
        "allowed_from": None, "requires": ["reason"]},
    "Return to Supplier": {"to_status": "Returned to Supplier", "to_location_type": "Supplier",
        "allowed_from": {"In Warehouse", "Returned", "Damaged", "Missing", "Under Repair"}, "requires": []},
}


def resolve_transition(movement_type, from_status):
    """Return the transition dict for the move, or raise if it is illegal
    from the unit's current status."""
    t = TRANSITIONS.get(movement_type)
    if not t:
        frappe.throw(_("Unknown movement type: {0}").format(movement_type))
    allowed = t["allowed_from"]
    if allowed is not None and from_status not in allowed:
        frappe.throw(_("Cannot '{0}' a unit that is '{1}'. Allowed only from: {2}.").format(
            movement_type, from_status, ", ".join(sorted(allowed))))
    return t
