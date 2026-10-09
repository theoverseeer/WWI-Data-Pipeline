-- dim_employee (SCD Type 1): people who are employees and/or salespeople.
-- Grain: one row per person. Unknown member: employee_key = -1.
CREATE OR REPLACE TABLE dim_employee AS
WITH src AS (
    SELECT
        wwi_int(PersonID) AS person_id,
        wwi_text(FullName) AS full_name,
        wwi_text(PreferredName) AS preferred_name,
        COALESCE(wwi_bool(IsEmployee), FALSE) AS is_employee,
        COALESCE(wwi_bool(IsSalesperson), FALSE) AS is_salesperson
    FROM application.people
)
SELECT ROW_NUMBER() OVER (ORDER BY person_id) AS employee_key, *
FROM src
WHERE is_employee OR is_salesperson
UNION ALL
SELECT -1, NULL, 'Unknown', 'Unknown', FALSE, FALSE;
