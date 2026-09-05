-- =============================================================================
-- schema.sql — baseline table definitions (version 1)
-- =============================================================================
-- This file is the single source of truth for the initial table shapes.
-- It is executed automatically by migrations/0001_initial_schema.sql the
-- first time the project runs against a fresh database. It is NOT re-run on
-- every startup — once applied, all further changes must arrive as new
-- files under database/migrations/.
--
-- Conventions:
--   * every table uses a UUID primary key (gen_random_uuid()), never
--     auto-increment integers.
--   * every table has created_at; tables that get mutated after insert also
--     have updated_at (kept current by the trigger in triggers.sql).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------------------------------------------------------
-- topics — the fixed set of content categories (Psychology, Science, ...)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS topics (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL UNIQUE,
    slug                TEXT NOT NULL UNIQUE,
    current_weight      NUMERIC(10, 4) NOT NULL DEFAULT 1.0,
    avg_performance     NUMERIC(10, 4),
    avg_reach           NUMERIC(14, 4),
    avg_saves           NUMERIC(14, 4),
    posts_count         INTEGER NOT NULL DEFAULT 0,
    last_updated_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- posts — one row per content post (the aggregate root)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS posts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category                TEXT,
    topic_id                UUID REFERENCES topics(id) ON DELETE SET NULL,
    final_text              TEXT,
    prompt_version          TEXT,
    status                  TEXT NOT NULL DEFAULT 'draft'
                                CHECK (status IN (
                                    'draft', 'ready', 'scheduled', 'publishing',
                                    'published', 'failed', 'cleaned'
                                )),
    scheduled_at            TIMESTAMPTZ,
    published_at            TIMESTAMPTZ,
    instagram_media_id      TEXT,
    instagram_permalink     TEXT,
    plan_id                 UUID,  -- id of the monthly/daily plan that produced this post (no FK: plan table is external/spreadsheet-origin today)
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- designs — visual/text-layout properties used to render a post's image
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS designs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id             UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    image_source        TEXT,
    image_url           TEXT,
    background_type     TEXT,
    dominant_color      TEXT,
    brightness          NUMERIC(6, 3),
    contrast            NUMERIC(6, 3),
    font_family         TEXT,
    font_size           INTEGER,
    font_color          TEXT,
    shadow              BOOLEAN NOT NULL DEFAULT FALSE,
    alignment           TEXT,
    line_count          INTEGER,
    word_count          INTEGER,
    image_score         NUMERIC(6, 3),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- media — raw/derived media assets for a post
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS media (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id                 UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    original_image_url      TEXT,
    original_image_source   TEXT,
    final_video_url         TEXT,
    video_duration_seconds  NUMERIC(6, 2),
    audio_used              TEXT,
    instagram_audio_id      TEXT,
    audio_reference_url     TEXT,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- publishing_schedule — the plan of when/why each post is due to publish
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS publishing_schedule (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id             UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    scheduled_at        TIMESTAMPTZ NOT NULL,
    priority            INTEGER NOT NULL DEFAULT 0,
    selection_reason    TEXT,
    status              TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'locked', 'done', 'cancelled')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- publishing_history — every publish attempt, including failures
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS publishing_history (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id             UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    started_at          TIMESTAMPTZ NOT NULL,
    ended_at            TIMESTAMPTZ,
    attempt_number      INTEGER NOT NULL DEFAULT 1,
    result               TEXT NOT NULL CHECK (result IN ('success', 'failure')),
    error_message        TEXT,
    duration_ms           INTEGER,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- metrics — periodic performance snapshots per post (NOT one row per post)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metrics (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id             UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    snapshot_period     TEXT NOT NULL CHECK (snapshot_period IN ('2h', '6h', '24h', '7d')),
    captured_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    views               BIGINT,
    reach               BIGINT,
    likes               BIGINT,
    comments            BIGINT,
    shares              BIGINT,
    saves               BIGINT,
    engagement_rate     NUMERIC(7, 4),
    followers           BIGINT,
    impressions         BIGINT,
    profile_visits      BIGINT,
    accounts_reached    BIGINT,
    accounts_engaged    BIGINT,
    UNIQUE (post_id, snapshot_period)
);
