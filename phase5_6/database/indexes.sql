-- =============================================================================
-- indexes.sql — baseline indexes (version 1)
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_posts_status            ON posts (status);
CREATE INDEX IF NOT EXISTS idx_posts_scheduled_at       ON posts (scheduled_at);
CREATE INDEX IF NOT EXISTS idx_posts_topic_id           ON posts (topic_id);
CREATE INDEX IF NOT EXISTS idx_posts_instagram_media_id ON posts (instagram_media_id);

CREATE INDEX IF NOT EXISTS idx_designs_post_id ON designs (post_id);
CREATE INDEX IF NOT EXISTS idx_media_post_id   ON media (post_id);

CREATE INDEX IF NOT EXISTS idx_publishing_schedule_status_time
    ON publishing_schedule (status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_publishing_schedule_post_id
    ON publishing_schedule (post_id);

CREATE INDEX IF NOT EXISTS idx_publishing_history_post_id
    ON publishing_history (post_id);
CREATE INDEX IF NOT EXISTS idx_publishing_history_result
    ON publishing_history (result);

CREATE INDEX IF NOT EXISTS idx_metrics_post_id_period ON metrics (post_id, snapshot_period);
CREATE INDEX IF NOT EXISTS idx_metrics_captured_at     ON metrics (captured_at);
