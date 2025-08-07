frappe.pages['stock-qty'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Stock Quantity Details',
        single_column: true
    });

    let filter_html = `
        <div class="stock-qty-filters row mb-3">
            <div class="col-sm-3 mb-2">
                <select class="form-control" id="so_filter">
                    <option value="">Sales Order ID</option>
                </select>
            </div>
            <div class="col-sm-3 mb-2">
                <input type="date" class="form-control" id="from_date">
            </div>
            <div class="col-sm-3 mb-2">
                <input type="date" class="form-control" id="to_date">
            </div>
            <div class="col-sm-3">
                <button class="btn btn-primary w-100" id="apply_filters"><i class="fa fa-filter"></i> Apply Filters</button>
            </div>
        </div>
    `;
    $(page.body).append(filter_html);

    $(page.body).append(`
        <style>
        .stock-qty-filters select, 
        .stock-qty-filters input, 
        .stock-qty-filters button {
            border-radius: 4px;
        }
        .stock-qty-container table {
            font-size: 13px;
            background: #fff;
            margin-top: 10px;
        }
        .stock-qty-container th {
            background: #f8fafc;
            font-weight: 700;
        }
        .stock-qty-container td, .stock-qty-container th {
            padding: 6px !important;
        }
        </style>
        <div class="stock-qty-container">
            <div id="stock_qty_data"></div>
        </div>
    `);

    // Populate Sales Order dropdown on load
    frappe.call({
        method: 'chundakadan.chundakadan.page.stock_qty.stock_qty.get_sales_order_list',
        callback: function(r) {
            if(r.message && $.isArray(r.message)) {
                const so_filter = $("#so_filter");
                r.message.forEach(so => {
                    so_filter.append(`<option value="${so.name}">${so.name}</option>`);
                });
            }
        }
    });

    // Bind filter button click
    $('#apply_filters').on('click', function() {
        get_and_display_data();
    });

    // Initial load
    get_and_display_data();
};

function get_and_display_data() {
    let filters = {
        sales_order: $('#so_filter').val(),
        from_date: $('#from_date').val(),
        to_date: $('#to_date').val()
    };

    frappe.call({
        method: 'chundakadan.chundakadan.page.stock_qty.stock_qty.get_so_details',
        args: { filters: filters },
        callback: function(r) {
            display_data(r.message || []);
        }
    });
}

function display_data(data) {
    let html = `
        <table class="table table-bordered table-sm">
            <thead>
                <tr>
                    <th>Sales Order</th>
                    <th>Status</th>
                    <th>Customer</th>
                    <th>Date</th>
                    <th>Item Code</th>
                    <th>Ordered Qty</th>
                    <th>Warehouse</th>
                    <th>Stock Qty</th>
                    <th>Remaining Qty</th>
                    <th>Remaining Qty to Invoice</th>
                </tr>
            </thead>
            <tbody>
    `;
    if (!data.length) {
        html += `<tr><td colspan="10" class="text-center text-muted">No Records Found</td></tr>`;
    } else {
        data.forEach(row => {
            html += `
                <tr>
                    <td>${row.sales_order}</td>
                    <td>${row.status || ''}</td>
                    <td>${row.customer}</td>
                    <td>${frappe.datetime.str_to_user(row.date)}</td>
                    <td>${row.item_code}</td>
                    <td>${row.ordered_qty}</td>
                    <td>${row.warehouse}</td>
                    <td>${row.stock_qty}</td>
                    <td>${row.remaining_qty}</td>
                    <td>${row.qty_to_invoice}</td>
                </tr>
            `;
        });
    }
    html += '</tbody></table>';
    $('#stock_qty_data').html(html);
}