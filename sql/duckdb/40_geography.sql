-- Q4 Place: where requests come from, and whether some areas wait longer for the same work.

-- Wait percentile: where a request's time to close falls inside its own request type and
-- year (0 = fastest, 1 = slowest, ties take the midpoint). Averaged over an area, 0.50 is
-- typical. This controls for request mix: a neighborhood full of weed complaints is not
-- penalized for weeds being slow citywide.
CREATE OR REPLACE TABLE field_wait_ranked AS
SELECT
    request_id,
    nbhd_id,
    council_district,
    request_type,
    created_year,
    hours_to_close,
    (percent_rank() OVER w + cume_dist() OVER w) / 2 AS wait_pct
FROM field_closed
WHERE request_type IN (SELECT request_type FROM top_field_types)
WINDOW w AS (PARTITION BY request_type, created_year ORDER BY hours_to_close);

CREATE OR REPLACE TABLE agg_neighborhood AS
WITH volume AS (
    SELECT
        nbhd_id,
        COUNT(*) AS field_requests,
        COUNT(*) FILTER (WHERE created_year = 2025) AS field_requests_2025,
        AVG((NOT is_closed)::INT) AS share_open_in_file,
        mode(request_category) AS top_category
    FROM field_requests
    WHERE nbhd_id IS NOT NULL
    GROUP BY nbhd_id
), wait AS (
    SELECT nbhd_id, AVG(wait_pct) AS wait_index, COUNT(*) AS ranked_requests,
           quantile_cont(hours_to_close, 0.5) / 24 AS p50_days
    FROM field_wait_ranked
    WHERE nbhd_id IS NOT NULL
    GROUP BY nbhd_id
)
SELECT
    n.nbhd_id,
    n.neighborhood,
    n.council_district,
    n.population,
    n.per_capita_income,
    n.pct_poverty,
    n.pct_renters,
    n.centroid_lat,
    n.centroid_lon,
    v.field_requests,
    v.field_requests_2025,
    v.field_requests / 7.0 / NULLIF(n.population, 0) * 1000 AS field_requests_per_1k_per_year,
    v.top_category,
    v.share_open_in_file,
    w.wait_index,
    w.ranked_requests,
    w.p50_days
FROM neighborhoods n
LEFT JOIN volume v USING (nbhd_id)
LEFT JOIN wait w USING (nbhd_id)
ORDER BY w.wait_index DESC;

CREATE OR REPLACE TABLE agg_neighborhood_category AS
SELECT
    f.nbhd_id,
    n.neighborhood,
    f.request_category,
    COUNT(*) AS field_requests,
    COUNT(*) / 7.0 / NULLIF(ANY_VALUE(n.population), 0) * 1000 AS per_1k_per_year
FROM field_requests f
JOIN neighborhoods n USING (nbhd_id)
GROUP BY ALL
ORDER BY f.nbhd_id, field_requests DESC;

CREATE OR REPLACE TABLE agg_council_district AS
WITH pop AS (
    SELECT council_district, SUM(population) AS population FROM neighborhoods GROUP BY 1
)
SELECT
    r.council_district,
    COUNT(*) AS ranked_requests,
    AVG(r.wait_pct) AS wait_index,
    quantile_cont(r.hours_to_close, 0.5) / 24 AS p50_days,
    ANY_VALUE(pop.population) AS approx_population
FROM field_wait_ranked r
LEFT JOIN pop USING (council_district)
WHERE r.council_district IS NOT NULL
GROUP BY r.council_district
ORDER BY r.council_district;

-- ~500 m grid cells for hotspot maps (0.005 degrees latitude is about 550 m in Denver).
CREATE OR REPLACE TABLE agg_hotspots AS
SELECT
    round(latitude / 0.005) * 0.005   AS cell_lat,
    round(longitude / 0.005) * 0.005  AS cell_lon,
    request_category,
    COUNT(*) AS field_requests
FROM field_requests
WHERE latitude IS NOT NULL
GROUP BY ALL
HAVING COUNT(*) >= 25
ORDER BY field_requests DESC;
