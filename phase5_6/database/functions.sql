-- =============================================================================
-- functions.sql — baseline functions (version 1)
-- =============================================================================

-- Generic "keep updated_at current" trigger function, reused by triggers.sql
-- on every table that has an updated_at column.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Recomputes topics.posts_count / avg_performance / avg_reach / avg_saves
-- from the metrics + posts tables. Called by repositories after a metrics
-- snapshot is written, rather than being wired to a trigger, so it can run
-- as a single explicit, observable step instead of firing on every insert.
CREATE OR REPLACE FUNCTION refresh_topic_stats(p_topic_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE topics t
    SET
        posts_count      = sub.posts_count,
        avg_reach        = sub.avg_reach,
        avg_saves        = sub.avg_saves,
        avg_performance  = sub.avg_engagement_rate,
        last_updated_at  = now()
    FROM (
        SELECT
            p.topic_id,
            COUNT(DISTINCT p.id)                    AS posts_count,
            AVG(m.reach)                             AS avg_reach,
            AVG(m.saves)                             AS avg_saves,
            AVG(m.engagement_rate)                   AS avg_engagement_rate
        FROM posts p
        LEFT JOIN metrics m ON m.post_id = p.id AND m.snapshot_period = '24h'
        WHERE p.topic_id = p_topic_id
        GROUP BY p.topic_id
    ) sub
    WHERE t.id = sub.topic_id;
END;
$$ LANGUAGE plpgsql;
