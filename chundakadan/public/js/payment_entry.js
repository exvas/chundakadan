frappe.ui.form.on("Payment Entry", {
    onload_post_render(frm) {
        setTimeout(() => {
            set_sales_person(frm);
        }, 500);
    }
});

function set_sales_person(frm) {

    if (frm.doc.custom_sales_persons) return;

    if (!frm.doc.references?.length) return;

    let sales_invoice = frm.doc.references.find(
        row => row.reference_doctype === "Sales Invoice"
    );

    if (!sales_invoice?.reference_name) return;

    frappe.db.get_value(
        "Sales Invoice",
        sales_invoice.reference_name,
        "custom_sales_person"
    ).then(r => {

        if (r.message?.custom_sales_person) {

            frm.set_value(
                "custom_sales_persons",
                r.message.custom_sales_person
            );
        }
    });
}