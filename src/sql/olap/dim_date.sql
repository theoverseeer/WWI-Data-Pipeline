-- dim_date: one row per calendar day plus an Unknown member (date_key = -1).
-- WWI financial year starts on 1 November and is named after the year it ends in
-- (1 Nov 2012 -> FY2013, fiscal month 1).
CREATE OR REPLACE TABLE dim_date AS
WITH cal AS (
    SELECT CAST(datum AS DATE) AS full_date
    FROM GENERATE_SERIES(DATE '2012-01-01', DATE '2030-12-31', INTERVAL '1 day') AS generated_dates(datum)
)
SELECT
    CAST(STRFTIME(full_date, '%Y%m%d') AS INTEGER) AS date_key,
    full_date,
    YEAR(full_date) AS year,
    QUARTER(full_date) AS quarter,
    MONTH(full_date) AS month,
    STRFTIME(full_date, '%B') AS month_name,
    STRFTIME(full_date, '%Y-%m') AS year_month,
    DAY(full_date) AS day_of_month,
    DAYOFWEEK(full_date) AS day_of_week,
    STRFTIME(full_date, '%A') AS day_name,
    DAYOFWEEK(full_date) IN (0, 6) AS is_weekend,
    YEAR(full_date) + CASE WHEN MONTH(full_date) >= 11 THEN 1 ELSE 0 END AS fiscal_year,
    'FY' || CAST(YEAR(full_date) + CASE WHEN MONTH(full_date) >= 11 THEN 1 ELSE 0 END AS VARCHAR) AS fiscal_year_label,
    CAST(CEIL(((MONTH(full_date) + 1) % 12 + 1) / 3.0) AS INTEGER) AS fiscal_quarter,
    (MONTH(full_date) + 1) % 12 + 1 AS fiscal_month_number
FROM cal
UNION ALL
SELECT -1, NULL, NULL, NULL, NULL, 'Unknown', 'Unknown', NULL, NULL, 'Unknown', NULL, NULL, 'Unknown', NULL, NULL;
