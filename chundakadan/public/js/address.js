// Copyright (c) 2026, Chundakadan and contributors
const GST_API = "chundakadan.doc_events.address_gst";

frappe.ui.form.on("Address", {
	refresh(frm) {
		offer_state_fix(frm, false);
	},

	gstin(frm) {
		offer_state_fix(frm, true);
	},
});

// India Compliance blocks the save when the GSTIN's state code and the
// State disagree, without saying which State the code belongs to. Tell the
// user, and let them decide — nothing changes on its own.
function offer_state_fix(frm, ask) {
	const gstin = (frm.doc.gstin || "").trim();
	if (gstin.length < 2 || frm.doc.country !== "India") return;

	frappe.xcall(`${GST_API}.state_for_gstin`, { gstin }).then((state) => {
		if (!state || state === frm.doc.state) return;

		const message = __("GSTIN {0} belongs to <b>{1}</b>, but this address says <b>{2}</b>.", [
			gstin.slice(0, 2),
			state,
			frm.doc.state || __("no state"),
		]);

		frm.dashboard.clear_headline();
		frm.dashboard.set_headline(message, "orange");

		frm.add_custom_button(__("Set State to {0}", [state]), () => frm.set_value("state", state));

		if (ask) {
			frappe.confirm(`${message}<br><br>${__("Change the State to {0}?", [state])}`, () =>
				frm.set_value("state", state)
			);
		}
	});
}
