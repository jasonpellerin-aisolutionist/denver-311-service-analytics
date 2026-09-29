-- PostgreSQL mirror of the core DuckDB analysis (sql/duckdb/10-40).
-- load_postgres.py compares these against DuckDB and fails on any mismatch.

SET search_path TO denver311;

CREATE VIEW field_requests AS
SELECT * FROM requests WHERE is_field_request;

CREATE VIEW field_closed AS
SELECT * FROM field_requests WHERE is_closed AND hours_to_close IS NOT NULL;

CREATE MATERIALIZED VIEW mv_yearly AS
SELECT
    created_year                                                               AS year,
    COUNT(*)                                                                   AS contacts,
    COUNT(*) FILTER (WHERE is_field_request)                                   AS field_requests,
    COUNT(*) FILTER (WHERE is_field_request AND request_type NOT ILIKE 'SWM%') AS field_requests_like_for_like,
    COUNT(*) FILTER (WHERE hours_to_close <= 0.25)                             AS handled_on_contact,
    COUNT(*) FILTER (WHERE NOT is_closed)                                      AS open_in_file
FROM requests
GROUP BY created_year
ORDER BY year;

CREATE MATERIALIZED VIEW mv_top_field_types AS
SELECT
    request_type,
    mode() WITHIN GROUP (ORDER BY request_category) AS request_category,
    mode() WITHIN GROUP (ORDER BY agency)           AS agency,
    COUNT(*)                                        AS requests_total
FROM field_requests
GROUP BY request_type
HAVING COUNT(DISTINCT created_year) = 7
ORDER BY requests_total DESC
LIMIT 25;

CREATE MATERIALIZED VIEW mv_type_year AS
WITH bench AS (
    SELECT request_type,
           percentile_cont(0.9) WITHIN GROUP (ORDER BY hours_to_close) AS p90_hours_2019
    FROM field_closed
    WHERE created_year = 2019
    GROUP BY request_type
)
SELECT
    f.request_type,
    f.created_year                                                                      AS year,
    COUNT(*)                                                                            AS requests,
    COUNT(*) FILTER (WHERE NOT f.is_closed)                                             AS open_in_file,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY f.hours_to_close)                       AS p50_hours,
    percentile_cont(0.9) WITHIN GROUP (ORDER BY f.hours_to_close)                       AS p90_hours,
    AVG((f.is_closed AND f.hours_to_close <= b.p90_hours_2019)::int)                    AS share_within_2019_p90
FROM field_requests f
JOIN mv_top_field_types t USING (request_type)
JOIN bench b USING (request_type)
GROUP BY f.request_type, f.created_year
ORDER BY f.request_type, year;

CREATE MATERIALIZED VIEW mv_channel_year AS
SELECT
    created_year AS year,
    channel,
    COUNT(*) AS contacts,
    COUNT(*) FILTER (WHERE is_field_request) AS field_requests
FROM requests
GROUP BY created_year, channel
ORDER BY year, contacts DESC;

CREATE MATERIALIZED VIEW mv_neighborhood_wait AS
WITH ranked AS (
    SELECT
        nbhd_id,
        (percent_rank() OVER w + cume_dist() OVER w) / 2 AS wait_pct
    FROM field_closed
    WHERE request_type IN (SELECT request_type FROM mv_top_field_types)
    WINDOW w AS (PARTITION BY request_type, created_year ORDER BY hours_to_close)
)
SELECT
    n.nbhd_id,
    n.neighborhood,
    n.population,
    COUNT(r.*)       AS ranked_requests,
    AVG(r.wait_pct)  AS wait_index
FROM neighborhoods n
LEFT JOIN ranked r USING (nbhd_id)
GROUP BY n.nbhd_id, n.neighborhood, n.population
ORDER BY wait_index DESC NULLS LAST;

CREATE UNIQUE INDEX ON mv_yearly (year);
CREATE UNIQUE INDEX ON mv_type_year (request_type, year);
CREATE UNIQUE INDEX ON mv_channel_year (year, channel);
CREATE UNIQUE INDEX ON mv_neighborhood_wait (nbhd_id);
