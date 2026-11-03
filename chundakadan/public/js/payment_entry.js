// The customer already names a sales person; fill it in rather than asking
// for it again. Only when the box is empty — whoever is already on the
// document was put there on purpose, or came in from the mobile app.
function cdn_fill_sales_person_from_customer(frm, customer) {
	if (!customer || frm.doc.custom_sales_person) return;
	frappe.call({
		method: "chundakadan.doc_events.sales_person_default.get_sales_person_for_customer",
		args: { customer: customer },
		callback: function (r) {
			if (r.message && !frm.doc.custom_sales_person) {
				frm.set_value("custom_sales_person", r.message);
			}
		},
	});
}

frappe.ui.form.on("Payment Entry", {
	party(frm) {
		if (frm.doc.party_type === "Customer") {
			cdn_fill_sales_person_from_customer(frm, frm.doc.party);
		}
	},

	setup(frm) {
		keep_cheque_out_of_cancel_all(frm);
	},

	refresh(frm) {
		// ERPNext assigns this list in its own onload, which runs after our
		// setup and would wipe ours — so add it again on every refresh.
		keep_cheque_out_of_cancel_all(frm);
	},

	onload_post_render(frm) {
		setTimeout(() => {
			set_sales_person(frm);
		}, 500);
	},
});

function set_sales_person(frm) {
	// custom_sales_person is the field every report reads; the older
	// custom_sales_persons is kept in step on the server for Cheque Bounce
	if (frm.doc.custom_sales_person) return;

	if (!frm.doc.references?.length) return;

	let sales_invoice = frm.doc.references.find(
		(row) => row.reference_doctype === "Sales Invoice"
	);

	if (!sales_invoice?.reference_name) return;

	frappe.db
		.get_value("Sales Invoice", sales_invoice.reference_name, "custom_sales_person")
		.then((r) => {
			if (r.message?.custom_sales_person) {
				frm.set_value("custom_sales_person", r.message.custom_sales_person);
			}
		});
}

// Cancelling a payment must never cancel the cheque behind it: the server
// puts the cheque back a step instead (Collected -> Pending). Listing it
// here keeps it out of the "Cancel All Documents" prompt.
function keep_cheque_out_of_cancel_all(frm) {
	const ignored = frm.ignore_doctypes_on_cancel_all || [];
	if (!ignored.includes("Post Dated Cheque")) ignored.push("Post Dated Cheque");
	frm.ignore_doctypes_on_cancel_all = ignored;
}
