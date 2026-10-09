-- fact_sale. GRAIN: one row per customer invoice line (sales.invoice_lines).
-- Customer and bill-to customer are resolved to the version valid on the invoice date.
-- Profit comes from the source LineProfit. Missing delivery dates map to the Unknown date (-1).
CREATE OR REPLACE TABLE fact_sale AS
WITH il AS (
    SELECT
        wwi_int(InvoiceLineID) AS invoice_line_id,
        wwi_int(InvoiceID) AS invoice_id,
        wwi_int(StockItemID) AS stock_item_id,
        wwi_int(Quantity) AS quantity,
        wwi_dec2(UnitPrice) AS unit_price,
        wwi_dec3(TaxRate) AS tax_rate,
        wwi_dec2(TaxAmount) AS tax_amount,
        wwi_dec2(LineProfit) AS profit,
        wwi_dec2(ExtendedPrice) AS total_including_tax
    FROM sales.invoice_lines
),
i AS (
    SELECT
        wwi_int(InvoiceID) AS invoice_id,
        wwi_int(OrderID) AS order_id,
        wwi_int(CustomerID) AS customer_id,
        wwi_int(BillToCustomerID) AS bill_to_customer_id,
        wwi_int(SalespersonPersonID) AS salesperson_id,
        wwi_date(InvoiceDate) AS invoice_date,
        CAST(wwi_ts(ConfirmedDeliveryTime) AS DATE) AS delivery_date
    FROM sales.invoices
),
o AS (
    SELECT wwi_int(OrderID) AS order_id, wwi_date(OrderDate) AS order_date
    FROM sales.orders
),
base AS (
    SELECT
        il.invoice_line_id,
        il.invoice_id,
        i.order_id,
        il.stock_item_id,
        il.quantity,
        il.unit_price,
        il.tax_rate,
        il.tax_amount,
        il.total_including_tax - il.tax_amount AS total_excluding_tax,
        il.total_including_tax,
        il.profit,
        DATEDIFF('day', o.order_date, i.invoice_date) AS days_order_to_invoice,
        DATEDIFF('day', i.invoice_date, i.delivery_date) AS days_invoice_to_delivery,
        i.invoice_date,
        i.delivery_date,
        i.customer_id,
        i.bill_to_customer_id,
        i.salesperson_id
    FROM il
    LEFT JOIN i ON i.invoice_id = il.invoice_id
    LEFT JOIN o ON o.order_id = i.order_id
)
SELECT
    b.invoice_line_id,
    b.invoice_id,
    b.order_id,
    COALESCE(dc.customer_key, -1) AS customer_key,
    COALESCE(dbt.customer_key, -1) AS bill_to_customer_key,
    COALESCE(dci.city_key, -1) AS city_key,
    COALESCE(dsi.stock_item_key, -1) AS stock_item_key,
    COALESCE(dsp.employee_key, -1) AS salesperson_key,
    COALESCE(dd_i.date_key, -1) AS invoice_date_key,
    COALESCE(dd_d.date_key, -1) AS delivery_date_key,
    b.quantity,
    b.unit_price,
    b.tax_rate,
    b.tax_amount,
    b.total_excluding_tax,
    b.total_including_tax,
    b.profit,
    b.days_order_to_invoice,
    b.days_invoice_to_delivery
FROM base b
LEFT JOIN asb_olap.dim_customer dc ON dc.customer_id = b.customer_id AND b.invoice_date BETWEEN dc.effective_start_date AND dc.effective_end_date
LEFT JOIN asb_olap.dim_customer dbt ON dbt.customer_id = b.bill_to_customer_id AND b.invoice_date BETWEEN dbt.effective_start_date AND dbt.effective_end_date
LEFT JOIN asb_olap.dim_city dci ON dci.city_id = dc.delivery_city_id
LEFT JOIN asb_olap.dim_stock_item dsi ON dsi.stock_item_id = b.stock_item_id
LEFT JOIN asb_olap.dim_employee dsp ON dsp.person_id = b.salesperson_id
LEFT JOIN asb_olap.dim_date dd_i ON dd_i.full_date = b.invoice_date
LEFT JOIN asb_olap.dim_date dd_d ON dd_d.full_date = b.delivery_date;
