import frappe, json

def update():
    path = "/Users/sammishthundiyil/frappe-bench-15/apps/chundakadan/chundakadan/chundakadan/print_format/quotation/quotation.json"
    with open(path) as f:
        data = json.load(f)
    pf = frappe.get_doc("Print Format", "Quotation")
    pf.html = data["html"]
    pf.css = data["css"]
    pf.save()
    return f"Updated. Length={len(pf.html)} header={'header-html' in pf.html} footer={'footer-html' in pf.html}"
