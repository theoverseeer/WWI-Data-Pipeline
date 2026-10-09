-- Product categories (stock groups). An item can be in several groups (many-to-many),
-- so groups live in a bridge table, not in dim_stock_item or the facts.
-- Summing facts by group counts an item once per group it belongs to (see README).
CREATE OR REPLACE TABLE bridge_stock_item_group AS
SELECT
    d.stock_item_key,
    wwi_int(g.StockGroupID) AS stock_group_id,
    wwi_text(g.StockGroupName) AS stock_group_name
FROM warehouse.stock_item_stock_groups ig
JOIN warehouse.stock_groups g ON wwi_int(ig.StockGroupID) = wwi_int(g.StockGroupID)
JOIN asb_olap.dim_stock_item d ON d.stock_item_id = wwi_int(ig.StockItemID);
