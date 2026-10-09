-- dim_city (SCD Type 1): city + state/province + country, read from the OLTP tables.
-- Grain: one row per city. Unknown member: city_key = -1.
CREATE OR REPLACE TABLE dim_city AS
WITH src AS (
    SELECT
        wwi_int(c.CityID) AS city_id,
        wwi_text(c.CityName) AS city_name,
        wwi_text(sp.StateProvinceCode) AS state_province_code,
        wwi_text(sp.StateProvinceName) AS state_province_name,
        wwi_text(sp.SalesTerritory) AS sales_territory,
        wwi_text(co.CountryName) AS country_name,
        wwi_text(co.FormalName) AS formal_name,
        wwi_text(co.Continent) AS continent,
        wwi_text(co.Region) AS region,
        wwi_text(co.Subregion) AS subregion,
        wwi_dbl(c.Latitude) AS latitude,
        wwi_dbl(c.Longitude) AS longitude,
        wwi_int(c.LatestRecordedPopulation) AS latest_recorded_population
    FROM application.cities c
    LEFT JOIN application.state_provinces sp ON wwi_int(c.StateProvinceID) = wwi_int(sp.StateProvinceID)
    LEFT JOIN application.countries co ON wwi_int(sp.CountryID) = wwi_int(co.CountryID)
)
SELECT ROW_NUMBER() OVER (ORDER BY city_id) AS city_key, * FROM src
UNION ALL
SELECT -1, NULL, 'Unknown', 'N/A', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', NULL, NULL, NULL;
