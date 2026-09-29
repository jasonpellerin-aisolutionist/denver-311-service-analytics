-- Q2 Speed: time from 311 case creation to 311 case closure for field requests.
-- There is no published SLA column, so each type is benchmarked against its own 2019 P90.

-- The 25 highest-volume field request types that appear in all seven years,
-- so every trend line compares the same thing.
CREATE OR REPLACE TABLE top_field_types AS
SELECT
    request_type,
    mode(request_category)          AS request_category,
    mode(agency)                    AS agency,
    COUNT(*)                        AS requests_total,
    COUNT(DISTINCT created_year)    AS years_present
FROM field_requests
GROUP BY request_type
HAVING COUNT(DISTINCT created_year) = 7
ORDER BY requests_total DESC
LIMIT 25;

CREATE OR REPLACE TABLE type_benchmark_2019 AS
SELECT
    request_type,
    quantile_cont(hours_to_close, 0.5) AS p50_hours_2019,
    quantile_cont(hours_to_close, 0.9) AS p90_hours_2019
FROM field_closed
WHERE created_year = 2019 AND request_type IN (SELECT request_type FROM top_field_types)
GROUP BY request_type;

-- Record integrity: a type-year whose closures are missing or stamped in one batch cannot
-- be read as a speed measurement.
CREATE OR REPLACE TABLE agg_closure_integrity AS
WITH per_day AS (
    SELECT request_type, created_year, closed_at::DATE AS close_day, COUNT(*) AS n
    FROM field_closed
    WHERE request_type IN (SELECT request_type FROM top_field_types)
    GROUP BY 1, 2, 3
), top_day AS (
    SELECT request_type, created_year, arg_max(close_day, n) AS top_close_day,
           MAX(n) / SUM(n) AS top_close_day_share
    FROM per_day
    GROUP BY 1, 2
), open_share AS (
    SELECT request_type, created_year, AVG((NOT is_closed)::INT) AS open_in_file_share
    FROM field_requests
    WHERE request_type IN (SELECT request_type FROM top_field_types)
    GROUP BY 1, 2
)
SELECT
    o.request_type,
    o.created_year AS year,
    o.open_in_file_share,
    t.top_close_day,
    t.top_close_day_share,
    o.open_in_file_share > 0.20 OR t.top_close_day_share > 0.25 AS record_gap
FROM open_share o
JOIN top_day t USING (request_type, created_year)
ORDER BY o.request_type, year;

CREATE OR REPLACE TABLE agg_type_year AS
SELECT
    t.request_type,
    t.request_category,
    t.agency,
    t.requests_total,
    f.created_year                                                         AS year,
    COUNT(*)                                                               AS requests,
    COUNT(*) FILTER (WHERE f.is_closed)                                    AS closed,
    COUNT(*) FILTER (WHERE NOT f.is_closed)                                AS open_in_file,
    quantile_cont(f.hours_to_close, 0.5)                                   AS p50_hours,
    quantile_cont(f.hours_to_close, 0.9)                                   AS p90_hours,
    AVG((f.hours_to_close <= 1)::INT)   FILTER (WHERE f.is_closed)         AS share_closed_within_1h,
    AVG((f.hours_to_close > 720)::INT)  FILTER (WHERE f.is_closed)         AS share_closed_after_30d,
    b.p50_hours_2019,
    b.p90_hours_2019,
    -- Open cases count as a miss: they were never closed inside the benchmark.
    AVG((f.is_closed AND f.hours_to_close <= b.p90_hours_2019)::INT)       AS share_within_2019_p90,
    ANY_VALUE(i.record_gap)                                                AS record_gap
FROM field_requests f
JOIN top_field_types t USING (request_type)
JOIN type_benchmark_2019 b USING (request_type)
JOIN agg_closure_integrity i ON i.request_type = f.request_type AND i.year = f.created_year
GROUP BY ALL
ORDER BY t.requests_total DESC, year;

-- Seven-year summary per type, for the ranked chart.
CREATE OR REPLACE TABLE agg_type_summary AS
SELECT
    t.request_type,
    t.request_category,
    t.agency,
    t.requests_total,
    quantile_cont(f.hours_to_close, 0.5) / 24                              AS p50_days,
    quantile_cont(f.hours_to_close, 0.9) / 24                              AS p90_days,
    AVG((f.hours_to_close <= 1)::INT)   FILTER (WHERE f.is_closed)         AS share_closed_within_1h,
    AVG((f.hours_to_close > 720)::INT)  FILTER (WHERE f.is_closed)         AS share_closed_after_30d,
    AVG((NOT f.is_closed)::INT)                                            AS share_open_in_file
FROM field_requests f
JOIN top_field_types t USING (request_type)
GROUP BY ALL
ORDER BY p90_days DESC;

CREATE OR REPLACE TABLE agg_agency_year AS
SELECT
    agency,
    created_year                           AS year,
    COUNT(*)                               AS field_requests,
    quantile_cont(hours_to_close, 0.5)     AS p50_hours,
    quantile_cont(hours_to_close, 0.9)     AS p90_hours,
    AVG((NOT is_closed)::INT)              AS share_open_in_file
FROM field_requests
GROUP BY ALL
HAVING COUNT(*) >= 500
ORDER BY agency, year;

-- Field requests with no close timestamp in the published file, by the year they came in.
CREATE OR REPLACE TABLE agg_open_backlog AS
SELECT
    created_year AS year,
    request_category,
    COUNT(*) AS open_in_file,
    COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY created_year) AS share_of_year_backlog
FROM field_requests
WHERE NOT is_closed
GROUP BY 1, 2
ORDER BY year, open_in_file DESC;
