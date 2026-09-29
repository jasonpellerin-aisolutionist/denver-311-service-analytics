-- Q1 Demand: how much comes in, what kind, and when.

-- What a 311 contact actually is, by year.
CREATE OR REPLACE TABLE agg_yearly AS
SELECT
    created_year                                                           AS year,
    COUNT(*)                                                               AS contacts,
    COUNT(*) FILTER (WHERE is_field_request)                               AS field_requests,
    -- Solid-waste (SWM) request types leave the 311 file after 2020, so year-over-year
    -- comparisons use a like-for-like basket that excludes them.
    COUNT(*) FILTER (WHERE is_field_request AND request_type NOT ILIKE 'SWM%') AS field_requests_like_for_like,
    COUNT(*) FILTER (WHERE request_type ILIKE 'SWM%')                      AS swm_contacts,
    COUNT(*) FILTER (WHERE status_group = 'answered' AND NOT has_location) AS answered_information,
    COUNT(*) FILTER (WHERE status_group = 'transferred')                   AS transferred_out,
    COUNT(*) FILTER (WHERE status_group = 'out_of_jurisdiction')           AS out_of_jurisdiction,
    COUNT(*) FILTER (WHERE status_group = 'invalid')                       AS invalid,
    COUNT(*) FILTER (WHERE hours_to_close <= 0.25)                         AS handled_on_contact,
    COUNT(*) FILTER (WHERE NOT is_closed)                                  AS open_in_file
FROM requests
GROUP BY 1
ORDER BY 1;

CREATE OR REPLACE TABLE agg_category_year AS
SELECT
    created_year AS year,
    request_category,
    COUNT(*) AS contacts,
    COUNT(*) FILTER (WHERE is_field_request) AS field_requests,
    COUNT(*) FILTER (WHERE is_field_request)
        / SUM(COUNT(*) FILTER (WHERE is_field_request)) OVER (PARTITION BY created_year) AS share_of_field
FROM requests
GROUP BY 1, 2
ORDER BY year, field_requests DESC;

CREATE OR REPLACE TABLE agg_monthly_category AS
SELECT
    created_month AS month,
    request_category,
    COUNT(*) AS contacts,
    COUNT(*) FILTER (WHERE is_field_request) AS field_requests
FROM requests
GROUP BY ALL
ORDER BY month, request_category;

-- Seasonal index: average field requests in a calendar month divided by that category's
-- average month. 1.0 is a typical month; 2.0 is double.
CREATE OR REPLACE TABLE agg_seasonality AS
WITH monthly AS (
    SELECT request_category, created_year, month(created_at) AS month_of_year, COUNT(*) AS n
    FROM field_requests
    GROUP BY ALL
), avg_month AS (
    SELECT request_category, month_of_year, AVG(n) AS avg_requests
    FROM monthly
    GROUP BY ALL
)
SELECT
    request_category,
    month_of_year,
    avg_requests,
    avg_requests / AVG(avg_requests) OVER (PARTITION BY request_category) AS seasonal_index
FROM avg_month
ORDER BY request_category, month_of_year;

CREATE OR REPLACE TABLE agg_hour_dow AS
SELECT created_dow AS dow, created_hour AS hour, COUNT(*) AS field_requests
FROM field_requests
GROUP BY ALL
ORDER BY dow, hour;
