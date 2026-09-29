-- Data quality checks. Each row is one check; `passed` must be true before analysis runs.

CREATE OR REPLACE TABLE quality_checks AS
WITH checks AS (
    SELECT 'request_id is unique' AS check_name,
           COUNT(*) - COUNT(DISTINCT request_id) AS failing_rows,
           0 AS tolerance
    FROM requests
    UNION ALL
    SELECT 'created_at is never null', COUNT(*) FILTER (WHERE created_at IS NULL), 0 FROM requests
    UNION ALL
    SELECT 'created year matches file year', COUNT(*) FILTER (WHERE created_year <> file_year), 0 FROM requests
    UNION ALL
    SELECT 'created_at within 2019-2025',
           COUNT(*) FILTER (WHERE created_at < TIMESTAMP '2019-01-01' OR created_at >= TIMESTAMP '2026-01-01'), 0
    FROM requests
    UNION ALL
    SELECT 'hours_to_close is non-negative', COUNT(*) FILTER (WHERE hours_to_close < 0), 0 FROM requests
    UNION ALL
    SELECT 'closed rows have a duration',
           COUNT(*) FILTER (WHERE is_closed AND hours_to_close IS NULL AND NOT flag_closed_before_created), 0
    FROM requests
    UNION ALL
    SELECT 'coordinates inside Denver box',
           COUNT(*) FILTER (WHERE latitude NOT BETWEEN 39.60 AND 39.92 OR longitude NOT BETWEEN -105.12 AND -104.59), 0
    FROM requests
    UNION ALL
    SELECT 'council district in 1-11', COUNT(*) FILTER (WHERE council_district NOT BETWEEN 1 AND 11), 0 FROM requests
    UNION ALL
    SELECT 'every row has a category', COUNT(*) FILTER (WHERE request_category IS NULL), 0 FROM requests
    UNION ALL
    -- Points on the city edge, at DIA, or in enclaves fall outside the 78 statistical
    -- neighborhoods, so a small miss rate is expected.
    SELECT 'geocoded rows matched to a neighborhood (<3% miss)',
           COUNT(*) FILTER (WHERE latitude IS NOT NULL AND nbhd_id IS NULL),
           CAST(0.03 * COUNT(*) FILTER (WHERE latitude IS NOT NULL) AS BIGINT)
    FROM requests
    UNION ALL
    SELECT 'neighborhood population sums to ACS total (+/- 1%)',
           CASE WHEN ABS(SUM(population) - 713734) <= 7137 THEN 0 ELSE 1 END, 0
    FROM neighborhoods
)
SELECT check_name, failing_rows, tolerance, failing_rows <= tolerance AS passed
FROM checks;

SELECT * FROM quality_checks;
