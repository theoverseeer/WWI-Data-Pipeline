-- Typed OLTP tables with primary and foreign keys.
-- Generated from src/oltp_typed.py (python src/oltp_typed.py). Parents first.

CREATE TABLE application.delivery_methods (
    "DeliveryMethodID" INTEGER PRIMARY KEY,
    "DeliveryMethodName" VARCHAR
);

CREATE TABLE application.countries (
    "CountryID" INTEGER PRIMARY KEY,
    "CountryName" VARCHAR,
    "FormalName" VARCHAR,
    "LatestRecordedPopulation" BIGINT,
    "Continent" VARCHAR,
    "Region" VARCHAR,
    "Subregion" VARCHAR
);

CREATE TABLE application.state_provinces (
    "StateProvinceID" INTEGER PRIMARY KEY,
    "StateProvinceCode" VARCHAR,
    "StateProvinceName" VARCHAR,
    "CountryID" INTEGER,
    "SalesTerritory" VARCHAR,
    "LatestRecordedPopulation" BIGINT,
    FOREIGN KEY ("CountryID") REFERENCES application.countries ("CountryID")
);

CREATE TABLE application.cities (
    "CityID" INTEGER PRIMARY KEY,
    "CityName" VARCHAR,
    "StateProvinceID" INTEGER,
    "Latitude" DOUBLE,
    "Longitude" DOUBLE,
    "LatestRecordedPopulation" BIGINT,
    FOREIGN KEY ("StateProvinceID") REFERENCES application.state_provinces ("StateProvinceID")
);

CREATE TABLE application.people (
    "PersonID" INTEGER PRIMARY KEY,
    "FullName" VARCHAR,
    "PreferredName" VARCHAR,
    "SearchName" VARCHAR,
    "IsEmployee" BOOLEAN,
    "IsSalesperson" BOOLEAN
);

CREATE TABLE sales.buying_groups (
    "BuyingGroupID" INTEGER PRIMARY KEY,
    "BuyingGroupName" VARCHAR
);

CREATE TABLE sales.customer_categories (
    "CustomerCategoryID" INTEGER PRIMARY KEY,
    "CustomerCategoryName" VARCHAR
);

CREATE TABLE purchasing.supplier_categories (
    "SupplierCategoryID" INTEGER PRIMARY KEY,
    "SupplierCategoryName" VARCHAR
);

CREATE TABLE warehouse.colors (
    "ColorID" INTEGER PRIMARY KEY,
    "ColorName" VARCHAR
);

CREATE TABLE warehouse.package_types (
    "PackageTypeID" INTEGER PRIMARY KEY,
    "PackageTypeName" VARCHAR
);

CREATE TABLE warehouse.stock_groups (
    "StockGroupID" INTEGER PRIMARY KEY,
    "StockGroupName" VARCHAR
);

CREATE TABLE purchasing.suppliers (
    "SupplierID" INTEGER PRIMARY KEY,
    "SupplierName" VARCHAR,
    "SupplierCategoryID" INTEGER,
    "PrimaryContactPersonID" INTEGER,
    "AlternateContactPersonID" INTEGER,
    "DeliveryMethodID" INTEGER,
    "DeliveryCityID" INTEGER,
    "PostalCityID" INTEGER,
    "SupplierReference" VARCHAR,
    "PaymentDays" INTEGER,
    "PhoneNumber" VARCHAR,
    "WebsiteURL" VARCHAR,
    "DeliveryAddressLine" VARCHAR,
    "DeliveryLocationLat" DOUBLE,
    "DeliveryLocationLong" DOUBLE,
    FOREIGN KEY ("SupplierCategoryID") REFERENCES purchasing.supplier_categories ("SupplierCategoryID"),
    FOREIGN KEY ("PrimaryContactPersonID") REFERENCES application.people ("PersonID"),
    FOREIGN KEY ("AlternateContactPersonID") REFERENCES application.people ("PersonID"),
    FOREIGN KEY ("DeliveryMethodID") REFERENCES application.delivery_methods ("DeliveryMethodID"),
    FOREIGN KEY ("DeliveryCityID") REFERENCES application.cities ("CityID"),
    FOREIGN KEY ("PostalCityID") REFERENCES application.cities ("CityID")
);

CREATE TABLE sales.customers (
    "CustomerID" INTEGER PRIMARY KEY,
    "CustomerName" VARCHAR,
    "BillToCustomerID" INTEGER,
    "CustomerCategoryID" INTEGER,
    "BuyingGroupID" INTEGER,
    "PrimaryContactPersonID" INTEGER,
    "AlternateContactPersonID" INTEGER,
    "DeliveryMethodID" INTEGER,
    "DeliveryCityID" INTEGER,
    "CreditLimit" DECIMAL(18,2),
    "AccountOpenedDate" DATE,
    "StandardDiscountPercentage" DECIMAL(18,3),
    "IsStatementSent" BOOLEAN,
    "IsOnCreditHold" BOOLEAN,
    "PaymentDays" INTEGER,
    "PhoneNumber" VARCHAR,
    "WebsiteURL" VARCHAR,
    "DeliveryAddressLine" VARCHAR,
    "DeliveryLocationLat" DOUBLE,
    "DeliveryLocationLong" DOUBLE,
    FOREIGN KEY ("CustomerCategoryID") REFERENCES sales.customer_categories ("CustomerCategoryID"),
    FOREIGN KEY ("BuyingGroupID") REFERENCES sales.buying_groups ("BuyingGroupID"),
    FOREIGN KEY ("PrimaryContactPersonID") REFERENCES application.people ("PersonID"),
    FOREIGN KEY ("AlternateContactPersonID") REFERENCES application.people ("PersonID"),
    FOREIGN KEY ("DeliveryMethodID") REFERENCES application.delivery_methods ("DeliveryMethodID"),
    FOREIGN KEY ("DeliveryCityID") REFERENCES application.cities ("CityID")
);

CREATE TABLE warehouse.stock_items (
    "StockItemID" INTEGER PRIMARY KEY,
    "StockItemName" VARCHAR,
    "SupplierID" INTEGER,
    "ColorID" INTEGER,
    "UnitPackageID" INTEGER,
    "OuterPackageID" INTEGER,
    "Brand" VARCHAR,
    "Size" VARCHAR,
    "LeadTimeDays" INTEGER,
    "QuantityPerOuter" INTEGER,
    "IsChillerStock" BOOLEAN,
    "Barcode" VARCHAR,
    "TaxRate" DECIMAL(18,3),
    "UnitPrice" DECIMAL(18,2),
    "RecommendedRetailPrice" DECIMAL(18,2),
    "TypicalWeightPerUnit" DECIMAL(18,3),
    FOREIGN KEY ("SupplierID") REFERENCES purchasing.suppliers ("SupplierID"),
    FOREIGN KEY ("ColorID") REFERENCES warehouse.colors ("ColorID"),
    FOREIGN KEY ("UnitPackageID") REFERENCES warehouse.package_types ("PackageTypeID"),
    FOREIGN KEY ("OuterPackageID") REFERENCES warehouse.package_types ("PackageTypeID")
);

CREATE TABLE warehouse.stock_item_stock_groups (
    "StockItemStockGroupID" INTEGER PRIMARY KEY,
    "StockItemID" INTEGER,
    "StockGroupID" INTEGER,
    FOREIGN KEY ("StockItemID") REFERENCES warehouse.stock_items ("StockItemID"),
    FOREIGN KEY ("StockGroupID") REFERENCES warehouse.stock_groups ("StockGroupID")
);

CREATE TABLE sales.orders (
    "OrderID" INTEGER PRIMARY KEY,
    "CustomerID" INTEGER,
    "SalespersonPersonID" INTEGER,
    "PickedByPersonID" INTEGER,
    "ContactPersonID" INTEGER,
    "BackorderOrderID" INTEGER,
    "OrderDate" DATE,
    "ExpectedDeliveryDate" DATE,
    "CustomerPurchaseOrderNumber" VARCHAR,
    "IsUndersupplyBackordered" BOOLEAN,
    "PickingCompletedWhen" TIMESTAMP,
    FOREIGN KEY ("CustomerID") REFERENCES sales.customers ("CustomerID"),
    FOREIGN KEY ("SalespersonPersonID") REFERENCES application.people ("PersonID"),
    FOREIGN KEY ("PickedByPersonID") REFERENCES application.people ("PersonID"),
    FOREIGN KEY ("ContactPersonID") REFERENCES application.people ("PersonID")
);

CREATE TABLE sales.order_lines (
    "OrderLineID" INTEGER PRIMARY KEY,
    "OrderID" INTEGER,
    "StockItemID" INTEGER,
    "Description" VARCHAR,
    "PackageTypeID" INTEGER,
    "Quantity" INTEGER,
    "UnitPrice" DECIMAL(18,2),
    "TaxRate" DECIMAL(18,3),
    "PickedQuantity" INTEGER,
    "PickingCompletedWhen" TIMESTAMP,
    FOREIGN KEY ("OrderID") REFERENCES sales.orders ("OrderID"),
    FOREIGN KEY ("StockItemID") REFERENCES warehouse.stock_items ("StockItemID"),
    FOREIGN KEY ("PackageTypeID") REFERENCES warehouse.package_types ("PackageTypeID")
);

CREATE TABLE sales.invoices (
    "InvoiceID" INTEGER PRIMARY KEY,
    "CustomerID" INTEGER,
    "BillToCustomerID" INTEGER,
    "OrderID" INTEGER,
    "DeliveryMethodID" INTEGER,
    "ContactPersonID" INTEGER,
    "AccountsPersonID" INTEGER,
    "SalespersonPersonID" INTEGER,
    "PackedByPersonID" INTEGER,
    "InvoiceDate" DATE,
    "CustomerPurchaseOrderNumber" VARCHAR,
    "DeliveryInstructions" VARCHAR,
    "TotalDryItems" INTEGER,
    "TotalChillerItems" INTEGER,
    "ConfirmedDeliveryTime" TIMESTAMP,
    "ConfirmedReceivedBy" VARCHAR,
    FOREIGN KEY ("CustomerID") REFERENCES sales.customers ("CustomerID"),
    FOREIGN KEY ("BillToCustomerID") REFERENCES sales.customers ("CustomerID"),
    FOREIGN KEY ("OrderID") REFERENCES sales.orders ("OrderID"),
    FOREIGN KEY ("DeliveryMethodID") REFERENCES application.delivery_methods ("DeliveryMethodID"),
    FOREIGN KEY ("ContactPersonID") REFERENCES application.people ("PersonID"),
    FOREIGN KEY ("AccountsPersonID") REFERENCES application.people ("PersonID"),
    FOREIGN KEY ("SalespersonPersonID") REFERENCES application.people ("PersonID"),
    FOREIGN KEY ("PackedByPersonID") REFERENCES application.people ("PersonID")
);

CREATE TABLE sales.invoice_lines (
    "InvoiceLineID" INTEGER PRIMARY KEY,
    "InvoiceID" INTEGER,
    "StockItemID" INTEGER,
    "Description" VARCHAR,
    "PackageTypeID" INTEGER,
    "Quantity" INTEGER,
    "UnitPrice" DECIMAL(18,2),
    "TaxRate" DECIMAL(18,3),
    "TaxAmount" DECIMAL(18,2),
    "LineProfit" DECIMAL(18,2),
    "ExtendedPrice" DECIMAL(18,2),
    FOREIGN KEY ("InvoiceID") REFERENCES sales.invoices ("InvoiceID"),
    FOREIGN KEY ("StockItemID") REFERENCES warehouse.stock_items ("StockItemID"),
    FOREIGN KEY ("PackageTypeID") REFERENCES warehouse.package_types ("PackageTypeID")
);
