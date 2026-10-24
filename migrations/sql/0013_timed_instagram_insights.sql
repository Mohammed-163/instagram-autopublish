-- Timed cumulative Instagram measurements. Safe to re-run; existing rows/tables
-- are preserved. The collector also creates this table on demand.
CREATE TABLE IF NOT EXISTS instagram_insight_snapshots (
    media_id TEXT NOT NULL,
    snapshot_period TEXT NOT NULL CHECK (snapshot_period IN ('1h','2h','6h','24h','3d','7d')),
    target_at TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    topic_slug TEXT,
    hook_line TEXT,
    ayah_key TEXT,
    ayah_text TEXT,
    iraqi_explanation TEXT,
    visual_style TEXT,
    music_file TEXT,
    reach BIGINT,
    saved BIGINT,
    shares BIGINT,
    likes BIGINT,
    comments BIGINT,
    views BIGINT,
    total_interactions BIGINT,
    PRIMARY KEY (media_id, snapshot_period)
);

-- Keep the existing UUID-linked metrics model compatible with the same periods.
ALTER TABLE metrics DROP CONSTRAINT IF EXISTS metrics_snapshot_period_check;
ALTER TABLE metrics ADD CONSTRAINT metrics_snapshot_period_check
    CHECK (snapshot_period IN ('1h','2h','6h','24h','3d','7d'));
