-- fact_order. GRAIN: one row per customer order line (sales.order_lines).
-- Dimension keys are resolved with the customer version valid on the order date.
-- Unmatched or missing dimension values map to the Unknown member (-1), so no row is dropped.
-- Invoiced quantity is matched through (order_id, stock_item_id), unique in this dataset.
CREATE OR REPLACE TABLE fact_order AS
WITH ol AS (
    SELECT
        wwi_int(OrderLineID) AS order_line_id,
        wwi_int(OrderID) AS order_id,
        wwi_int(StockItemID) AS stock_item_id,
        wwi_int(Quantity) AS quantity,
        wwi_dec2(UnitPrice) AS unit_price,
        wwi_dec3(TaxRate) AS tax_rate,
        wwi_int(PickedQuantity) AS picked_quantity
    FROM sales.order_lines
),
o AS (
    SELECT
        wwi_int(OrderID) AS order_id,
        wwi_int(CustomerID) AS customer_id,
        wwi_int(SalespersonPersonID) AS salesperson_id,
        wwi_int(PickedByPersonID) AS picker_id,
        wwi_int(BackorderOrderID) AS backorder_order_id,
        wwi_date(OrderDate) AS order_date,
        wwi_date(ExpectedDeliveryDate) AS expected_delivery_date,
        CAST(wwi_ts(PickingCompletedWhen) AS DATE) AS picked_date
    FROM sales.orders
),
inv AS (
    SELECT
        wwi_int(i.OrderID) AS order_id,
        wwi_int(l.StockItemID) AS stock_item_id,
        wwi_int(l.Quantity) AS invoiced_quantity,
        wwi_date(i.InvoiceDate) AS invoice_date
    FROM sales.invoice_lines l
    JOIN sales.invoices i ON wwi_int(l.InvoiceID) = wwi_int(i.InvoiceID)
),
base AS (
    SELECT
        ol.order_line_id,
        ol.order_id,
        o.backorder_order_id,
        ol.quantity,
        ol.picked_quantity,
        GREATEST(ol.quantity - COALESCE(ol.picked_quantity, ol.quantity), 0) AS backordered_quantity,
        COALESCE(inv.invoiced_quantity, 0) AS invoiced_quantity,
        ol.unit_price,
        ol.tax_rate,
        CAST(ol.quantity * ol.unit_price AS DECIMAL(18,2)) AS total_excluding_tax,
        CAST(ROUND(ol.quantity * ol.unit_price * ol.tax_rate / 100, 2) AS DECIMAL(18,2)) AS tax_amount,
        CAST(GREATEST(ol.quantity - COALESCE(ol.picked_quantity, ol.quantity), 0) * ol.unit_price AS DECIMAL(18,2)) AS backordered_amount_excluding_tax,
        DATEDIFF('day', o.order_date, inv.invoice_date) AS days_order_to_invoice,
        o.order_date,
        o.expected_delivery_date,
        o.picked_date,
        inv.invoice_date,
        o.customer_id,
        o.salesperson_id,
        o.picker_id,
        ol.stock_item_id
    FROM ol
    LEFT JOIN o ON o.order_id = ol.order_id
    LEFT JOIN inv ON inv.order_id = ol.order_id AND inv.stock_item_id = ol.stock_item_id
)
SELECT
    b.order_line_id,
    b.order_id,
    b.backorder_order_id,
    COALESCE(dc.customer_key, -1) AS customer_key,
    COALESCE(dci.city_key, -1) AS city_key,
    COALESCE(dsi.stock_item_key, -1) AS stock_item_key,
    COALESCE(dsp.employee_key, -1) AS salesperson_key,
    COALESCE(dpk.employee_key, -1) AS picker_key,
    COALESCE(dd_o.date_key, -1) AS order_date_key,
    COALESCE(dd_e.date_key, -1) AS expected_delivery_date_key,
    COALESCE(dd_p.date_key, -1) AS picked_date_key,
    COALESCE(dd_i.date_key, -1) AS invoice_date_key,
    b.quantity AS ordered_quantity,
    b.picked_quantity,
    b.backordered_quantity,
    b.backordered_quantity > 0 AS is_backordered,
    b.invoiced_quantity,
    b.unit_price,
    b.tax_rate,
    b.total_excluding_tax,
    b.tax_amount,
    b.total_excluding_tax + b.tax_amount AS total_including_tax,
    b.backordered_amount_excluding_tax,
    b.days_order_to_invoice
FROM base b
LEFT JOIN asb_olap.dim_customer dc ON dc.customer_id = b.customer_id AND b.order_date BETWEEN dc.effective_start_date AND dc.effective_end_date
LEFT JOIN asb_olap.dim_city dci ON dci.city_id = dc.delivery_city_id
LEFT JOIN asb_olap.dim_stock_item dsi ON dsi.stock_item_id = b.stock_item_id
LEFT JOIN asb_olap.dim_employee dsp ON dsp.person_id = b.salesperson_id
LEFT JOIN asb_olap.dim_employee dpk ON dpk.person_id = b.picker_id
LEFT JOIN asb_olap.dim_date dd_o ON dd_o.full_date = b.order_date
LEFT JOIN asb_olap.dim_date dd_e ON dd_e.full_date = b.expected_delivery_date
LEFT JOIN asb_olap.dim_date dd_p ON dd_p.full_date = b.picked_date
LEFT JOIN asb_olap.dim_date dd_i ON dd_i.full_date = b.invoice_date;
