"""Typed OLTP layer (imported by run_pipe.py).

The course boilerplate (src/01_ingest_csv.py) loads every CSV with types inferred by DuckDB and no
constraints. This module keeps that load untouched as a RAW LANDING copy (schema `landing`) and then
rebuilds the tables the warehouse needs, under the same schema.table names, with:

  * suitable data types (dd/mm/yyyy dates, decimals, booleans, decimal-comma coordinates, ...)
  * PRIMARY KEY and FOREIGN KEY constraints
  * the text NULL and empty strings turned into real nulls
  * duplicate primary keys removed (first row kept) and rejected rows written to etl.quarantine
  * a log of rows landed / loaded / rejected and of values that could not be converted
    (etl.oltp_hardening_log)

Run `python src/oltp_typed.py` to regenerate src/sql/oltp_typed/typed_tables.sql (the DDL for review).

Type tokens: INT BIGINT DEC2 DEC3 DATE TS BOOL DBLC TEXT (see CAST below).
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

SQL_TYPES = {
    "INT": "INTEGER", "BIGINT": "BIGINT", "DEC2": "DECIMAL(18,2)", "DEC3": "DECIMAL(18,3)",
    "DATE": "DATE", "TS": "TIMESTAMP", "BOOL": "BOOLEAN", "DBLC": "DOUBLE", "TEXT": "VARCHAR",
}
CAST = {  # conversion macros are defined in src/sql/macros.sql
    "INT": "wwi_int", "BIGINT": "wwi_bigint", "DEC2": "wwi_dec2", "DEC3": "wwi_dec3", "DATE": "wwi_date",
    "TS": "wwi_ts", "BOOL": "wwi_bool", "DBLC": "wwi_dbl", "TEXT": "wwi_text",
}


@dataclass
class TypedTable:
    schema: str
    table: str
    csv: str
    pk: str
    cols: list
    fks: list = field(default_factory=list)      # [(column, "schema.parent_table")]

    @property
    def name(self) -> str:                       # e.g. sales.customers
        return f"{self.schema}.{self.table}"

    @property
    def landing(self) -> str:                    # e.g. landing.sales_customers
        return f"landing.{self.schema}_{self.table}"


def T(schema, table, csv, pk, cols, fks=()):
    return TypedTable(schema, table, csv, pk, [tuple(c.split(":")) for c in cols.split()], list(fks))


# Parents first. Children are dropped in the reverse order.
TABLES = [
    T("application", "delivery_methods", "Application.DeliveryMethods.csv", "DeliveryMethodID",
      "DeliveryMethodID:INT DeliveryMethodName:TEXT"),
    T("application", "countries", "Application.Countries.csv", "CountryID",
      "CountryID:INT CountryName:TEXT FormalName:TEXT LatestRecordedPopulation:BIGINT "
      "Continent:TEXT Region:TEXT Subregion:TEXT"),
    T("application", "state_provinces", "Application.StateProvinces.csv", "StateProvinceID",
      "StateProvinceID:INT StateProvinceCode:TEXT StateProvinceName:TEXT CountryID:INT "
      "SalesTerritory:TEXT LatestRecordedPopulation:BIGINT",
      [("CountryID", "application.countries")]),
    T("application", "cities", "Application.Cities.csv", "CityID",
      "CityID:INT CityName:TEXT StateProvinceID:INT Latitude:DBLC Longitude:DBLC "
      "LatestRecordedPopulation:BIGINT",
      [("StateProvinceID", "application.state_provinces")]),
    T("application", "people", "Application.People.csv", "PersonID",
      "PersonID:INT FullName:TEXT PreferredName:TEXT SearchName:TEXT IsEmployee:BOOL IsSalesperson:BOOL"),
    T("sales", "buying_groups", "Sales.BuyingGroups.csv", "BuyingGroupID",
      "BuyingGroupID:INT BuyingGroupName:TEXT"),
    T("sales", "customer_categories", "Sales.CustomerCategories.csv", "CustomerCategoryID",
      "CustomerCategoryID:INT CustomerCategoryName:TEXT"),
    T("purchasing", "supplier_categories", "Purchasing.SupplierCategories.csv", "SupplierCategoryID",
      "SupplierCategoryID:INT SupplierCategoryName:TEXT"),
    T("warehouse", "colors", "Warehouse.Colors.csv", "ColorID", "ColorID:INT ColorName:TEXT"),
    T("warehouse", "package_types", "Warehouse.PackageTypes.csv", "PackageTypeID",
      "PackageTypeID:INT PackageTypeName:TEXT"),
    T("warehouse", "stock_groups", "Warehouse.StockGroups.csv", "StockGroupID",
      "StockGroupID:INT StockGroupName:TEXT"),
    T("purchasing", "suppliers", "Purchasing.Suppliers.csv", "SupplierID",
      "SupplierID:INT SupplierName:TEXT SupplierCategoryID:INT PrimaryContactPersonID:INT "
      "AlternateContactPersonID:INT DeliveryMethodID:INT DeliveryCityID:INT PostalCityID:INT "
      "SupplierReference:TEXT PaymentDays:INT PhoneNumber:TEXT WebsiteURL:TEXT "
      "DeliveryAddressLine:TEXT DeliveryLocationLat:DBLC DeliveryLocationLong:DBLC",
      [("SupplierCategoryID", "purchasing.supplier_categories"), ("PrimaryContactPersonID", "application.people"),
       ("AlternateContactPersonID", "application.people"), ("DeliveryMethodID", "application.delivery_methods"),
       ("DeliveryCityID", "application.cities"), ("PostalCityID", "application.cities")]),
    # Customers.BillToCustomerID references customers itself. It is not declared as a FOREIGN KEY
    # (a self-reference is fragile to bulk load); run_pipe.py checks it in validate_oltp.
    T("sales", "customers", "Sales.Customers.csv", "CustomerID",
      "CustomerID:INT CustomerName:TEXT BillToCustomerID:INT CustomerCategoryID:INT "
      "BuyingGroupID:INT PrimaryContactPersonID:INT AlternateContactPersonID:INT "
      "DeliveryMethodID:INT DeliveryCityID:INT CreditLimit:DEC2 AccountOpenedDate:DATE "
      "StandardDiscountPercentage:DEC3 IsStatementSent:BOOL IsOnCreditHold:BOOL PaymentDays:INT "
      "PhoneNumber:TEXT WebsiteURL:TEXT DeliveryAddressLine:TEXT DeliveryLocationLat:DBLC "
      "DeliveryLocationLong:DBLC",
      [("CustomerCategoryID", "sales.customer_categories"), ("BuyingGroupID", "sales.buying_groups"),
       ("PrimaryContactPersonID", "application.people"), ("AlternateContactPersonID", "application.people"),
       ("DeliveryMethodID", "application.delivery_methods"), ("DeliveryCityID", "application.cities")]),
    T("warehouse", "stock_items", "Warehouse.StockItems.csv", "StockItemID",
      "StockItemID:INT StockItemName:TEXT SupplierID:INT ColorID:INT UnitPackageID:INT "
      "OuterPackageID:INT Brand:TEXT Size:TEXT LeadTimeDays:INT QuantityPerOuter:INT "
      "IsChillerStock:BOOL Barcode:TEXT TaxRate:DEC3 UnitPrice:DEC2 RecommendedRetailPrice:DEC2 "
      "TypicalWeightPerUnit:DEC3",
      [("SupplierID", "purchasing.suppliers"), ("ColorID", "warehouse.colors"),
       ("UnitPackageID", "warehouse.package_types"), ("OuterPackageID", "warehouse.package_types")]),
    T("warehouse", "stock_item_stock_groups", "Warehouse.StockItemStockGroups.csv", "StockItemStockGroupID",
      "StockItemStockGroupID:INT StockItemID:INT StockGroupID:INT",
      [("StockItemID", "warehouse.stock_items"), ("StockGroupID", "warehouse.stock_groups")]),
    T("sales", "orders", "Sales.Orders.csv", "OrderID",
      "OrderID:INT CustomerID:INT SalespersonPersonID:INT PickedByPersonID:INT ContactPersonID:INT "
      "BackorderOrderID:INT OrderDate:DATE ExpectedDeliveryDate:DATE CustomerPurchaseOrderNumber:TEXT "
      "IsUndersupplyBackordered:BOOL PickingCompletedWhen:TS",
      [("CustomerID", "sales.customers"), ("SalespersonPersonID", "application.people"),
       ("PickedByPersonID", "application.people"), ("ContactPersonID", "application.people")]),
    T("sales", "order_lines", "Sales.OrderLines.csv", "OrderLineID",
      "OrderLineID:INT OrderID:INT StockItemID:INT Description:TEXT PackageTypeID:INT Quantity:INT "
      "UnitPrice:DEC2 TaxRate:DEC3 PickedQuantity:INT PickingCompletedWhen:TS",
      [("OrderID", "sales.orders"), ("StockItemID", "warehouse.stock_items"),
       ("PackageTypeID", "warehouse.package_types")]),
    T("sales", "invoices", "Sales.Invoices.csv", "InvoiceID",
      "InvoiceID:INT CustomerID:INT BillToCustomerID:INT OrderID:INT DeliveryMethodID:INT "
      "ContactPersonID:INT AccountsPersonID:INT SalespersonPersonID:INT PackedByPersonID:INT "
      "InvoiceDate:DATE CustomerPurchaseOrderNumber:TEXT DeliveryInstructions:TEXT TotalDryItems:INT "
      "TotalChillerItems:INT ConfirmedDeliveryTime:TS ConfirmedReceivedBy:TEXT",
      [("CustomerID", "sales.customers"), ("BillToCustomerID", "sales.customers"), ("OrderID", "sales.orders"),
       ("DeliveryMethodID", "application.delivery_methods"), ("ContactPersonID", "application.people"),
       ("AccountsPersonID", "application.people"), ("SalespersonPersonID", "application.people"),
       ("PackedByPersonID", "application.people")]),
    T("sales", "invoice_lines", "Sales.InvoiceLines.csv", "InvoiceLineID",
      "InvoiceLineID:INT InvoiceID:INT StockItemID:INT Description:TEXT PackageTypeID:INT Quantity:INT "
      "UnitPrice:DEC2 TaxRate:DEC3 TaxAmount:DEC2 LineProfit:DEC2 ExtendedPrice:DEC2",
      [("InvoiceID", "sales.invoices"), ("StockItemID", "warehouse.stock_items"),
       ("PackageTypeID", "warehouse.package_types")]),
]
BY_NAME = {t.name: t for t in TABLES}


def q(identifier: str) -> str:
    return '"' + identifier + '"'


# ----------------------------------------------------------------------------- DDL
def ddl_for(t: TypedTable) -> str:
    lines = []
    for col, typ in t.cols:
        lines.append(f"    {q(col)} {SQL_TYPES[typ]}" + (" PRIMARY KEY" if col == t.pk else ""))
    for col, parent in t.fks:
        if parent.split(".")[0] == t.schema:   # DuckDB can't create FKs across schemas
            lines.append(f"    FOREIGN KEY ({q(col)}) REFERENCES {parent} ({q(BY_NAME[parent].pk)})")




def full_ddl() -> str:
    head = ("-- Typed OLTP tables with primary and foreign keys.\n"
            "-- Generated from src/oltp_typed.py (python src/oltp_typed.py). Parents first.\n\n")
    return head + "\n\n".join(ddl_for(t) for t in TABLES) + "\n"


# ----------------------------------------------------------------------------- build
def drop_typed(con) -> None:
    """Drop the typed tables, children first (foreign keys block dropping a parent)."""
    for t in reversed(TABLES):
        con.execute(f"DROP TABLE IF EXISTS {t.name}")


def to_landing(con) -> None:
    """Move the boilerplate's raw tables into the landing schema (original values, untouched)."""
    con.execute("CREATE SCHEMA IF NOT EXISTS landing")
    for t in TABLES:
        # We split the name by the dot and quote the schema and table separately
        schema, table = t.name.split('.')
        land_schema, land_table = t.landing.split('.')
        
        con.execute(f'CREATE OR REPLACE TABLE "{land_schema}"."{land_table}" AS SELECT * FROM "{schema}"."{table}"')
        con.execute(f'DROP TABLE "{schema}"."{table}"')




def build_typed(con, run_id: str, load_no: int, log) -> None:
    """Rebuild every typed table from its landing copy. Idempotent: same landing data, same result."""
    drop_typed(con)
    for t in TABLES:
        started = datetime.now()
        con.execute(ddl_for(t))
        landed = con.execute(f"SELECT COUNT(*) FROM {t.landing}").fetchone()[0]

        # values that were present in the source but could not be converted (they become NULL)
        typed_cols = [(c, ty) for c, ty in t.cols if ty != "TEXT"]
        cast_failures = ""
        if typed_cols:
            parts = ", ".join(
                f"COUNT(*) FILTER (WHERE wwi_text({q(c)}) IS NOT NULL AND {CAST[ty]}({q(c)}) IS NULL)"
                for c, ty in typed_cols)
            counts = con.execute(f"SELECT {parts} FROM {t.landing}").fetchone()
            cast_failures = ", ".join(f"{c}:{n}" for (c, _), n in zip(typed_cols, counts) if n)

        # typed copy, then reject rules: null key, duplicate key (first row kept), orphan foreign key
        select_cols = ", ".join(f"{CAST[ty]}({q(c)}) AS {q(c)}" for c, ty in t.cols)
        con.execute(f"CREATE OR REPLACE TEMP TABLE stg_t AS SELECT {select_cols}, ROW_NUMBER() OVER () AS _rn FROM {t.landing}")
        pk = q(t.pk)
        fk_whens = "".join(
            f"WHEN {q(c)} IS NOT NULL AND {q(c)} NOT IN (SELECT {q(BY_NAME[p].pk)} FROM {p}) "
            f"THEN 'orphan foreign key {c}'\n"
            for c, p in t.fks)





        con.execute(f"""
            CREATE OR REPLACE TEMP TABLE chk_t AS
            SELECT *, CASE
                WHEN {pk} IS NULL THEN 'null primary key'
                WHEN ROW_NUMBER() OVER (PARTITION BY {pk} ORDER BY _rn) > 1 THEN 'duplicate primary key'
                {fk_whens}
            END AS _reason FROM stg_t""")
        col_list = ", ".join(q(c) for c, _ in t.cols)
        con.execute(f"INSERT INTO {t.name} ({col_list}) SELECT {col_list} FROM chk_t WHERE _reason IS NULL ORDER BY _rn")
        as_text = ", ".join(f"CAST({q(c)} AS VARCHAR)" for c, _ in t.cols)
        con.execute(f"""
            INSERT INTO asb_olap.etl.quarantine
            SELECT CAST(? AS VARCHAR), CAST(? AS VARCHAR), _rn, CAST({pk} AS VARCHAR), _reason,
                   concat_ws('|', {as_text}), now()
            FROM chk_t WHERE _reason IS NOT NULL""", [run_id, t.name])
        loaded = con.execute(f"SELECT COUNT(*) FROM {t.name}").fetchone()[0]
        rejected = landed - loaded
        con.execute("INSERT INTO asb_olap.etl.oltp_hardening_log VALUES (?,?,?,?,?,?,?,?)",
                    [run_id, load_no, t.name, landed, loaded, rejected, cast_failures or None, datetime.now()])
        con.execute("DROP TABLE IF EXISTS stg_t")
        con.execute("DROP TABLE IF EXISTS chk_t")
        msg = f"  typed {t.name:<34} landed={landed:>8,} loaded={loaded:>8,} rejected={rejected:>4}"
        if cast_failures:
            msg += f"  cast_failures=[{cast_failures}]"
        log.info(msg)



if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "sql" / "oltp_typed" / "typed_tables.sql"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(full_ddl(), encoding="utf-8")
    print("wrote", out)
