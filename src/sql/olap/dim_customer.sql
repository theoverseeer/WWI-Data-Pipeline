-- dim_customer: SCD Type 2 on customer category, buying group and delivery city.
-- Everything else (name, contact, credit limit, phone, ...) is SCD Type 1: overwritten on all versions.
-- Grain: one row per customer VERSION. Unknown member: customer_key = -1.
-- This script is incremental (history must survive), so it does NOT use CREATE OR REPLACE.
-- run_pipe.py replaces @EFFECTIVE_DATE@ and @RUN_ID@ and runs the statements in order.
-- Statement 1: target table (created on the first load, kept afterwards)
CREATE TABLE IF NOT EXISTS asb_olap.dim_customer (
    customer_key INTEGER,
    customer_id INTEGER,
    customer_name VARCHAR,
    bill_to_customer_id INTEGER,
    bill_to_customer_name VARCHAR,
    customer_category_name VARCHAR,
    buying_group_name VARCHAR,
    primary_contact_name VARCHAR,
    delivery_method_name VARCHAR,
    delivery_city_id INTEGER,
    delivery_city_name VARCHAR,
    delivery_state_province VARCHAR,
    credit_limit DECIMAL(18,2),
    payment_days INTEGER,
    account_opened_date DATE,
    standard_discount_percentage DECIMAL(18,3),
    is_on_credit_hold BOOLEAN,
    phone_number VARCHAR,
    website_url VARCHAR,
    delivery_address_line VARCHAR,
    scd_hash VARCHAR,
    effective_start_date DATE,
    effective_end_date DATE,
    is_current BOOLEAN,
    loaded_run_id VARCHAR,
    loaded_at TIMESTAMP
);
-- Statement 2: staging, the customers as they are in OLTP right now, with a hash of the Type 2 attributes
CREATE OR REPLACE TEMP TABLE stg_customer AS
WITH s AS (
    SELECT
        wwi_int(c.CustomerID) AS customer_id,
        wwi_text(c.CustomerName) AS customer_name,
        wwi_int(c.BillToCustomerID) AS bill_to_customer_id,
        wwi_text(b.CustomerName) AS bill_to_customer_name,
        COALESCE(wwi_text(cc.CustomerCategoryName), 'Unknown') AS customer_category_name,
        COALESCE(wwi_text(bg.BuyingGroupName), 'N/A') AS buying_group_name,
        wwi_text(p.FullName) AS primary_contact_name,
        wwi_text(dm.DeliveryMethodName) AS delivery_method_name,
        wwi_int(c.DeliveryCityID) AS delivery_city_id,
        wwi_text(ci.CityName) AS delivery_city_name,
        wwi_text(sp.StateProvinceName) AS delivery_state_province,
        wwi_dec2(c.CreditLimit) AS credit_limit,
        wwi_int(c.PaymentDays) AS payment_days,
        wwi_date(c.AccountOpenedDate) AS account_opened_date,
        wwi_dec3(c.StandardDiscountPercentage) AS standard_discount_percentage,
        wwi_bool(c.IsOnCreditHold) AS is_on_credit_hold,
        wwi_text(c.PhoneNumber) AS phone_number,
        wwi_text(c.WebsiteURL) AS website_url,
        wwi_text(c.DeliveryAddressLine) AS delivery_address_line
    FROM sales.customers c
    LEFT JOIN sales.customers b ON wwi_int(c.BillToCustomerID) = wwi_int(b.CustomerID)
    LEFT JOIN sales.customer_categories cc ON wwi_int(c.CustomerCategoryID) = wwi_int(cc.CustomerCategoryID)
    LEFT JOIN sales.buying_groups bg ON wwi_int(c.BuyingGroupID) = wwi_int(bg.BuyingGroupID)
    LEFT JOIN application.people p ON wwi_int(c.PrimaryContactPersonID) = wwi_int(p.PersonID)
    LEFT JOIN application.delivery_methods dm ON wwi_int(c.DeliveryMethodID) = wwi_int(dm.DeliveryMethodID)
    LEFT JOIN application.cities ci ON wwi_int(c.DeliveryCityID) = wwi_int(ci.CityID)
    LEFT JOIN application.state_provinces sp ON wwi_int(ci.StateProvinceID) = wwi_int(sp.StateProvinceID)
)
SELECT
    s.*,
    MD5(CONCAT_WS('|', customer_category_name, buying_group_name, COALESCE(CAST(delivery_city_id AS VARCHAR), ''))) AS scd_hash
FROM s;
-- Statement 3: customers whose current version differs from the source (Type 2 change detected)
CREATE OR REPLACE TEMP TABLE chg_customer AS
SELECT s.customer_id
FROM stg_customer s
JOIN asb_olap.dim_customer d ON d.customer_id = s.customer_id AND d.is_current
WHERE d.scd_hash <> s.scd_hash;
-- Statement 4: Type 1 attributes, overwritten on every version of the customer
UPDATE asb_olap.dim_customer AS d
SET customer_name = s.customer_name,
    bill_to_customer_id = s.bill_to_customer_id,
    bill_to_customer_name = s.bill_to_customer_name,
    primary_contact_name = s.primary_contact_name,
    delivery_method_name = s.delivery_method_name,
    credit_limit = s.credit_limit,
    payment_days = s.payment_days,
    account_opened_date = s.account_opened_date,
    standard_discount_percentage = s.standard_discount_percentage,
    is_on_credit_hold = s.is_on_credit_hold,
    phone_number = s.phone_number,
    website_url = s.website_url,
    delivery_address_line = s.delivery_address_line
FROM stg_customer s
WHERE d.customer_id = s.customer_id;
-- Statement 5: close the old version the day before the change takes effect
UPDATE asb_olap.dim_customer
SET effective_end_date = DATE '@EFFECTIVE_DATE@' - 1,
    is_current = FALSE
WHERE is_current
  AND customer_id IN (SELECT customer_id FROM chg_customer);
-- Statement 6: insert new versions (changed customers) and brand-new customers
INSERT INTO asb_olap.dim_customer (
    customer_key, customer_id, customer_name, bill_to_customer_id, bill_to_customer_name,
    customer_category_name, buying_group_name, primary_contact_name, delivery_method_name,
    delivery_city_id, delivery_city_name, delivery_state_province, credit_limit, payment_days,
    account_opened_date, standard_discount_percentage, is_on_credit_hold, phone_number, website_url,
    delivery_address_line, scd_hash, effective_start_date, effective_end_date, is_current,
    loaded_run_id, loaded_at)
SELECT
    (SELECT COALESCE(MAX(customer_key), 0) FROM asb_olap.dim_customer WHERE customer_key > 0)
        + ROW_NUMBER() OVER (ORDER BY s.customer_id) AS customer_key,
    s.customer_id, s.customer_name, s.bill_to_customer_id, s.bill_to_customer_name,
    s.customer_category_name, s.buying_group_name, s.primary_contact_name, s.delivery_method_name,
    s.delivery_city_id, s.delivery_city_name, s.delivery_state_province, s.credit_limit, s.payment_days,
    s.account_opened_date, s.standard_discount_percentage, s.is_on_credit_hold, s.phone_number, s.website_url,
    s.delivery_address_line, s.scd_hash,
    CASE
        WHEN EXISTS (SELECT 1 FROM asb_olap.dim_customer x WHERE x.customer_id = s.customer_id) THEN DATE '@EFFECTIVE_DATE@'
        WHEN (SELECT COUNT(*) FROM asb_olap.dim_customer WHERE customer_key > 0) = 0 THEN DATE '1900-01-01'
        ELSE DATE '@EFFECTIVE_DATE@'
    END AS effective_start_date,
    DATE '9999-12-31' AS effective_end_date,
    TRUE AS is_current,
    '@RUN_ID@' AS loaded_run_id,
    NOW() AS loaded_at
FROM stg_customer s
WHERE s.customer_id IN (SELECT customer_id FROM chg_customer)
   OR NOT EXISTS (SELECT 1 FROM asb_olap.dim_customer d WHERE d.customer_id = s.customer_id);
-- Statement 7: Unknown member for facts whose customer cannot be resolved
INSERT INTO asb_olap.dim_customer (
    customer_key, customer_id, customer_name, customer_category_name, buying_group_name,
    effective_start_date, effective_end_date, is_current, loaded_run_id, loaded_at)
SELECT -1, NULL, 'Unknown', 'Unknown', 'N/A', DATE '1900-01-01', DATE '9999-12-31', TRUE, '@RUN_ID@', NOW()
WHERE NOT EXISTS (SELECT 1 FROM asb_olap.dim_customer WHERE customer_key = -1);
