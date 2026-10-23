-- =============================================================================
-- views.sql — baseline views (version 1)
-- =============================================================================

-- Latest metrics snapshot per (post, period) combined into one row per post,
-- pivoted to the most recently captured snapshot of each period.
CREATE OR REPLACE VIEW v_latest_metrics AS
SELECT DISTINCT ON (post_id, snapshot_period)
    post_id,
    snapshot_period,
    captured_at,
    views,
    reach,
    likes,
    comments,
    shares,
    saves,
    engagement_rate,
    followers,
    impressions,
    profile_visits,
    accounts_reached,
    accounts_engaged
FROM metrics
ORDER BY post_id, snapshot_period, captured_at DESC;

-- One row per topic with its live rollup numbers, for quick reporting /
-- Telegram digest queries without joining across the whole schema each time.
CREATE OR REPLACE VIEW v_topic_performance AS
SELECT
    t.id,
    t.name,
    t.slug,
    t.current_weight,
    t.avg_performance,
    t.avg_reach,
    t.avg_saves,
    t.posts_count,
    t.last_updated_at
FROM topics t
ORDER BY t.avg_performance DESC NULLS LAST;

-- Posts currently due (scheduled but not yet published), for the publisher script.
CREATE OR REPLACE VIEW v_due_posts AS
SELECT
    p.id,
    p.category,
    p.topic_id,
    p.final_text,
    p.scheduled_at,
    ps.priority,
    ps.selection_reason
FROM posts p
JOIN publishing_schedule ps ON ps.post_id = p.id
WHERE p.status IN ('ready', 'scheduled')
  AND ps.status = 'pending'
  AND ps.scheduled_at <= now()
ORDER BY ps.priority DESC, ps.scheduled_at ASC;
