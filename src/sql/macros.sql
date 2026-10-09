-- Defensive conversion macros used by every OLAP script.
-- The boilerplate OLTP load keeps the CSV text as-is, so a column can hold the text NULL,
-- dd/mm/yyyy dates, 7-digit timestamps or decimal commas depending on how DuckDB sniffed it.
-- These macros give the same clean result whatever type the column ended up with.
CREATE OR REPLACE TEMP MACRO wwi_text(x) AS NULLIF(NULLIF(TRIM(CAST(x AS VARCHAR)), ''), 'NULL');
CREATE OR REPLACE TEMP MACRO wwi_int(x) AS TRY_CAST(TRY_CAST(wwi_text(x) AS DECIMAL(18,3)) AS INTEGER);
CREATE OR REPLACE TEMP MACRO wwi_dec2(x) AS TRY_CAST(wwi_text(x) AS DECIMAL(18,2));
CREATE OR REPLACE TEMP MACRO wwi_dec3(x) AS TRY_CAST(wwi_text(x) AS DECIMAL(18,3));
CREATE OR REPLACE TEMP MACRO wwi_dbl(x) AS TRY_CAST(REPLACE(wwi_text(x), ',', '.') AS DOUBLE);
CREATE OR REPLACE TEMP MACRO wwi_date(x) AS COALESCE(TRY_CAST(TRY_STRPTIME(wwi_text(x), '%d/%m/%Y') AS DATE), TRY_CAST(wwi_text(x) AS DATE));
CREATE OR REPLACE TEMP MACRO wwi_ts(x) AS TRY_CAST(SUBSTR(wwi_text(x), 1, 26) AS TIMESTAMP);
CREATE OR REPLACE TEMP MACRO wwi_bool(x) AS CASE WHEN LOWER(wwi_text(x)) IN ('1', 'true', 't') THEN TRUE WHEN LOWER(wwi_text(x)) IN ('0', 'false', 'f') THEN FALSE END;
