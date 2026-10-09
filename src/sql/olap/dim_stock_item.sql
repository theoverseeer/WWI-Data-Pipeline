-- dim_stock_item (SCD Type 1): product with color, brand, package and supplier attributes.
-- Grain: one row per stock item. Unknown member: stock_item_key = -1.
-- Brand/Color/Size are missing for most items in the source, so they become 'N/A' (as in WWI's DW).
CREATE OR REPLACE TABLE dim_stock_item AS
WITH src AS (
    SELECT
        wwi_int(s.StockItemID) AS stock_item_id,
        wwi_text(s.StockItemName) AS stock_item_name,
        COALESCE(wwi_text(col.ColorName), 'N/A') AS color_name,
        COALESCE(wwi_text(s.Brand), 'N/A') AS brand,
        COALESCE(wwi_text(s.Size), 'N/A') AS size,
        wwi_text(up.PackageTypeName) AS selling_package,
        wwi_text(op.PackageTypeName) AS buying_package,
        wwi_text(su.SupplierName) AS supplier_name,
        wwi_int(s.LeadTimeDays) AS lead_time_days,
        wwi_int(s.QuantityPerOuter) AS quantity_per_outer,
        COALESCE(wwi_bool(s.IsChillerStock), FALSE) AS is_chiller_stock,
        wwi_text(s.Barcode) AS barcode,
        wwi_dec3(s.TaxRate) AS tax_rate,
        wwi_dec2(s.UnitPrice) AS unit_price,
        wwi_dec2(s.RecommendedRetailPrice) AS recommended_retail_price,
        wwi_dec3(s.TypicalWeightPerUnit) AS typical_weight_per_unit
    FROM warehouse.stock_items s
    LEFT JOIN warehouse.colors col ON wwi_int(s.ColorID) = wwi_int(col.ColorID)
    LEFT JOIN warehouse.package_types up ON wwi_int(s.UnitPackageID) = wwi_int(up.PackageTypeID)
    LEFT JOIN warehouse.package_types op ON wwi_int(s.OuterPackageID) = wwi_int(op.PackageTypeID)
    LEFT JOIN purchasing.suppliers su ON wwi_int(s.SupplierID) = wwi_int(su.SupplierID)
)
SELECT ROW_NUMBER() OVER (ORDER BY stock_item_id) AS stock_item_key, * FROM src
UNION ALL
SELECT -1, NULL, 'Unknown', 'N/A', 'N/A', 'N/A', 'Unknown', 'Unknown', 'Unknown', NULL, NULL, FALSE, NULL, NULL, NULL, NULL, NULL;
