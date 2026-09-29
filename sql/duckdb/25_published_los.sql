-- Q2b Speed against the city's own goals.
-- DOTI publishes Level of Service (LOS) goals in business days for its most common request
-- types (denvergov.org, "Resident Level of Service for DOTI Requests", retrieved 2026-09-29).
-- Five of the top 25 field request types have a published goal. The goals are current, so
-- applying them to 2019-2024 is a retrospective comparison, not a record of the target in force.
-- Business days here exclude weekends but not city holidays, which makes the test slightly stricter.

CREATE OR REPLACE TABLE published_los AS
SELECT * FROM (VALUES
    ('Pothole', 5),
    ('Signal Hazard (Traffic)', 5),
    ('Transportation Signal Maintenance', 30),
    ('Transportation Sign Maintenance', 45),
    ('Signal Timing', 90)
) AS t(request_type, los_business_days);

CREATE OR REPLACE TABLE business_calendar AS
SELECT
    d::DATE AS day,
    SUM(CASE WHEN isodow(d) <= 5 THEN 1 ELSE 0 END) OVER (ORDER BY d) AS business_day_number
FROM generate_series(TIMESTAMP '2018-12-01', TIMESTAMP '2026-12-31', INTERVAL 1 DAY) AS g(d);

-- Open cases count as misses, matching the derived benchmark in 20_resolution_time.sql.
CREATE OR REPLACE TABLE agg_published_los AS
SELECT
    f.request_type,
    f.created_year                                                    AS year,
    l.los_business_days,
    COUNT(*)                                                          AS requests,
    COUNT(*) FILTER (WHERE f.is_closed)                               AS closed,
    AVG(CASE WHEN f.is_closed
             AND cc.business_day_number - cr.business_day_number <= l.los_business_days
        THEN 1 ELSE 0 END)                                            AS share_within_los,
    quantile_cont(cc.business_day_number - cr.business_day_number, 0.5)
        FILTER (WHERE f.is_closed)                                    AS p50_business_days,
    quantile_cont(cc.business_day_number - cr.business_day_number, 0.9)
        FILTER (WHERE f.is_closed)                                    AS p90_business_days,
    COALESCE(ci.record_gap, FALSE)                                    AS record_gap
FROM field_requests f
JOIN published_los l USING (request_type)
JOIN business_calendar cr ON cr.day = f.created_at::DATE
LEFT JOIN business_calendar cc ON cc.day = f.closed_at::DATE
LEFT JOIN agg_closure_integrity ci ON ci.request_type = f.request_type AND ci.year = f.created_year
GROUP BY f.request_type, f.created_year, l.los_business_days, ci.record_gap
ORDER BY f.request_type, year;
