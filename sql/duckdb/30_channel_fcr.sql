-- Q3 Channel: how requests arrive, and which phone volume could move to self-service.

CREATE OR REPLACE TABLE agg_channel_year AS
SELECT
    created_year AS year,
    channel,
    COUNT(*)                                   AS contacts,
    COUNT(*) FILTER (WHERE is_field_request)   AS field_requests,
    COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY created_year) AS share_of_contacts,
    COUNT(*) FILTER (WHERE is_field_request)
        / SUM(COUNT(*) FILTER (WHERE is_field_request)) OVER (PARTITION BY created_year) AS share_of_field
FROM requests
GROUP BY 1, 2
ORDER BY year, contacts DESC;

-- App share of each top field type, by year: which work moved to the app and which stayed on the phone.
CREATE OR REPLACE TABLE agg_type_channel_year AS
SELECT
    f.request_type,
    f.created_year AS year,
    COUNT(*) AS requests,
    AVG((f.channel = 'App (PocketGov)')::INT) AS app_share,
    AVG((f.channel = 'Phone')::INT)           AS phone_share
FROM field_requests f
WHERE f.request_type IN (SELECT request_type FROM top_field_types)
GROUP BY ALL
ORDER BY f.request_type, year;

-- Same request type, different channel: does the channel change time to close?
-- Only types with at least 500 closed requests on both channels are compared.
CREATE OR REPLACE TABLE agg_channel_speed AS
WITH by_channel AS (
    SELECT
        request_type,
        channel,
        COUNT(*) AS closed,
        quantile_cont(hours_to_close, 0.5) AS p50_hours
    FROM field_closed
    WHERE channel IN ('Phone', 'App (PocketGov)')
      AND request_type IN (SELECT request_type FROM top_field_types)
    GROUP BY ALL
)
SELECT
    p.request_type,
    p.closed      AS phone_closed,
    a.closed      AS app_closed,
    p.p50_hours   AS phone_p50_hours,
    a.p50_hours   AS app_p50_hours,
    a.p50_hours - p.p50_hours AS app_minus_phone_hours
FROM by_channel p
JOIN by_channel a ON a.request_type = p.request_type AND a.channel = 'App (PocketGov)'
WHERE p.channel = 'Phone' AND p.closed >= 500 AND a.closed >= 500
ORDER BY app_minus_phone_hours;

-- Deflection candidates: phone contacts with no location, answered and closed within
-- 15 minutes. These are questions a caller had answered on the spot, which a published
-- answer, app flow, or IVR message could handle instead.
CREATE OR REPLACE TABLE agg_deflection_candidates AS
WITH phone_info AS (
    SELECT request_type, request_category, created_year
    FROM requests
    WHERE channel = 'Phone'
      AND NOT has_location
      AND status_group = 'answered'
      AND hours_to_close <= 0.25
), totals AS (
    SELECT COUNT(*) AS phone_contacts FROM requests WHERE channel = 'Phone'
)
SELECT
    request_type,
    mode(request_category)                                AS request_category,
    COUNT(*)                                              AS answered_calls_7y,
    COUNT(*) FILTER (WHERE created_year = 2025)           AS answered_calls_2025,
    COUNT(*) / ANY_VALUE(totals.phone_contacts)           AS share_of_all_phone_contacts
FROM phone_info, totals
GROUP BY request_type
ORDER BY answered_calls_7y DESC
LIMIT 20;

-- The source First Call Resolution flag, for the record: it is Y on almost every row.
CREATE OR REPLACE TABLE agg_fcr_flag AS
SELECT
    created_year AS year,
    AVG(first_call_resolution::INT)        AS fcr_flag_share,
    AVG((hours_to_close <= 0.25)::INT)     AS closed_within_15m_share
FROM requests
GROUP BY 1
ORDER BY 1;
