-- Visitor-level behavioral features for segmentation.
-- Built entirely from events.csv fields (no category/price data is available
-- in the fixed source), so segments describe *engagement and purchase
-- behavior*, not product-taste personas.

CREATE OR REPLACE TABLE visitor_segmentation_features AS
WITH bounds AS (
    SELECT MAX(event_time_ms) AS max_event_time_ms
    FROM events_clean
),
visitor_events AS (
    SELECT
        visitor_id,
        event_time_ms,
        event_type,
        item_id
    FROM events_clean
)
SELECT
    summary.visitor_id,
    summary.session_count,
    summary.event_count AS total_events,
    summary.transaction_item_events,
    summary.ever_purchased,

    -- recency: days between the visitor's last event and the end of the
    -- observation window
    (bounds.max_event_time_ms - EXTRACT(EPOCH FROM summary.last_seen_utc) * 1000)
        / 86400000.0 AS recency_days,

    -- tenure: days between first and last observed activity
    DATE_DIFF('day', summary.first_seen_utc, summary.last_seen_utc)
        AS tenure_days,

    -- engagement depth
    ROUND(summary.event_count::DOUBLE / summary.session_count, 2)
        AS avg_events_per_session,
    sf.avg_session_duration_minutes,
    sf.unique_items_total,

    -- funnel behavior
    ROUND(
        100.0 * sf.cart_sessions / NULLIF(summary.session_count, 0), 2
    ) AS cart_session_rate_pct,
    ROUND(
        100.0 * sf.transaction_sessions / NULLIF(sf.cart_sessions, 0), 2
    ) AS cart_to_purchase_rate_pct,
    ROUND(
        100.0 * (summary.session_count - sf.view_only_sessions)
            / NULLIF(summary.session_count, 0), 2
    ) AS beyond_browse_session_rate_pct

FROM visitor_summary AS summary
CROSS JOIN bounds
JOIN (
    SELECT
        visitor_id,
        AVG(duration_minutes) AS avg_session_duration_minutes,
        SUM(unique_items) AS unique_items_total,
        COUNT(*) FILTER (WHERE cart_events > 0) AS cart_sessions,
        COUNT(*) FILTER (WHERE transaction_events > 0) AS transaction_sessions,
        COUNT(*) FILTER (
            WHERE cart_events = 0 AND transaction_events = 0
        ) AS view_only_sessions
    FROM session_facts
    GROUP BY visitor_id
) AS sf USING (visitor_id);
