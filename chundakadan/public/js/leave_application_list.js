// code written by niranjana nir
// Leave Application list customization

frappe.listview_settings['Leave Application'] = {

    get_indicator: function(doc) {

        let color = "gray";
        let label = doc.status;

        if (doc.status === "Approved") {
            color = "green";
        }

        else if (doc.status === "Pending") {
            color = "orange";
        }

        else if (doc.status === "Partially Approved") {
            color = "blue";
        }

        else if (doc.status === "Rejected") {
            color = "red";
        }

        else if (doc.status === "Draft") {
            color = "gray";
        }

        else if (doc.status === "Cancelled") {
            color = "darkgrey";
        }

        return [__(label), color, "status,=," + doc.status];
    },

    formatters: {

        custom_approval_status: function(value, df, doc) {

            if (!value) return '';

            let color = "gray";

            if (value === "Approved")
                color = "green";

            else if (value === "Pending")
                color = "orange";

            else if (value === "Partially Approved")
                color = "blue";

            else if (value === "Rejected")
                color = "red";

            else if (value === "Draft")
                color = "gray";

            else if (value === "Cancelled")
                color = "darkgrey";

            return `
                <span class="indicator-pill ${color}">
                    ${__(value)}
                </span>
            `;
        }
    }
};