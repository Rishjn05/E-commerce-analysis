-- Diagnostic breakdowns of cart abandonment and natural recovery.
-- These are associative cuts of observational data, not a causal analysis:
-- the source has no checkout, price, or acquisition fields, so this
-- identifies WHERE abandonment and recovery concentrate, not WHY a given
-- visitor abandoned.

CREATE OR REPLACE TABLE abandonment_with_context AS
SELECT
    abandonment.visitor_id,
    abandonment.session_number,
    abandonment.session_start_utc,
    abandonment.session_end_utc,
    sf.duration_minutes,
    sf.unique_items,
    sf.cart_events,
    CASE
        WHEN prior.session_count IS NULL OR prior.session_count = 0
            THEN 'new'
        ELSE 'returning'
    END AS visitor_status_at_abandonment,
    COALESCE(prior.session_count, 0) AS prior_session_count,
    recovery.next_transaction_ms IS NOT NULL
        AND recovery.next_transaction_ms
            <= abandonment.session_end_ms + 7 * 86400000
        AS recovered_within_7d
FROM first_cart_abandonment AS abandonment
JOIN session_facts AS sf
    ON sf.visitor_id = abandonment.visitor_id
    AND sf.session_number = abandonment.session_number
LEFT JOIN cart_recovery_events AS recovery
    ON recovery.visitor_id = abandonment.visitor_id
    AND recovery.session_number = abandonment.session_number
LEFT JOIN (
    SELECT
        visitor_id,
        session_number,
        session_number - 1 AS session_count
    FROM session_facts
) AS prior
    ON prior.visitor_id = abandonment.visitor_id
    AND prior.session_number = abandonment.session_number;

CREATE OR REPLACE TABLE abandonment_by_hour AS
SELECT
    EXTRACT(HOUR FROM session_end_utc)::INTEGER AS hour_of_day_utc,
    COUNT(*) AS abandoned_sessions,
    ROUND(100.0 * AVG(recovered_within_7d::INTEGER), 2)
        AS recovery_rate_7d_pct
FROM abandonment_with_context
GROUP BY hour_of_day_utc
ORDER BY hour_of_day_utc;

CREATE OR REPLACE TABLE abandonment_by_weekday AS
SELECT
    DAYNAME(session_end_utc) AS weekday,
    DAYOFWEEK(session_end_utc) AS weekday_number,
    COUNT(*) AS abandoned_sessions,
    ROUND(100.0 * AVG(recovered_within_7d::INTEGER), 2)
        AS recovery_rate_7d_pct
FROM abandonment_with_context
GROUP BY weekday, weekday_number
ORDER BY weekday_number;

CREATE OR REPLACE TABLE abandonment_by_duration_bucket AS
SELECT
    CASE
        WHEN duration_minutes < 1 THEN '01. under 1 min'
        WHEN duration_minutes < 5 THEN '02. 1-5 min'
        WHEN duration_minutes < 15 THEN '03. 5-15 min'
        WHEN duration_minutes < 30 THEN '04. 15-30 min'
        ELSE '05. 30+ min'
    END AS session_duration_bucket,
    COUNT(*) AS abandoned_sessions,
    ROUND(100.0 * AVG(recovered_within_7d::INTEGER), 2)
        AS recovery_rate_7d_pct
FROM abandonment_with_context
GROUP BY session_duration_bucket
ORDER BY session_duration_bucket;

CREATE OR REPLACE TABLE abandonment_by_cart_size AS
SELECT
    CASE
        WHEN unique_items = 1 THEN '01. single item'
        WHEN unique_items BETWEEN 2 AND 3 THEN '02. 2-3 items'
        ELSE '03. 4+ items'
    END AS cart_size_bucket,
    COUNT(*) AS abandoned_sessions,
    ROUND(100.0 * AVG(recovered_within_7d::INTEGER), 2)
        AS recovery_rate_7d_pct
FROM abandonment_with_context
GROUP BY cart_size_bucket
ORDER BY cart_size_bucket;

CREATE OR REPLACE TABLE abandonment_by_visitor_status AS
SELECT
    visitor_status_at_abandonment,
    COUNT(*) AS abandoned_sessions,
    ROUND(100.0 * AVG(recovered_within_7d::INTEGER), 2)
        AS recovery_rate_7d_pct
FROM abandonment_with_context
GROUP BY visitor_status_at_abandonment
ORDER BY visitor_status_at_abandonment;
