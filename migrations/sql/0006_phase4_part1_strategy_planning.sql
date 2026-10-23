-- Phase 4 Part 1 -- Strategy & Planning Layer (planning only, no execution)

CREATE TABLE IF NOT EXISTS hook_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    category TEXT,
    hook_text TEXT NOT NULL,
    hook_type TEXT NOT NULL,
    features JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hook_patterns_post_id ON hook_patterns(post_id);
CREATE INDEX IF NOT EXISTS idx_hook_patterns_category_hook_type ON hook_patterns(category, hook_type);

CREATE TABLE IF NOT EXISTS hook_statistics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category TEXT NOT NULL,
    hook_type TEXT NOT NULL,
    sample_size INTEGER NOT NULL DEFAULT 0,
    success_sum NUMERIC(12,4) NOT NULL DEFAULT 0,
    avg_success_score NUMERIC(6,4) NOT NULL DEFAULT 0,
    success_level TEXT NOT NULL DEFAULT 'low',
    confidence NUMERIC(5,4) NOT NULL DEFAULT 0,
    is_rule BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_hook_statistics_category_hook_type UNIQUE (category, hook_type)
);

CREATE TABLE IF NOT EXISTS weekly_strategy_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_number INTEGER NOT NULL UNIQUE,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_weekly_strategy_versions_week_start ON weekly_strategy_versions(week_start);

CREATE TABLE IF NOT EXISTS strategy_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_version_id UUID NOT NULL REFERENCES weekly_strategy_versions(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    category TEXT NOT NULL,
    topic TEXT NOT NULL,
    hook_type TEXT NOT NULL,
    objective TEXT NOT NULL,
    reason TEXT NOT NULL,
    confidence NUMERIC(5,4) NOT NULL DEFAULT 0,
    expected_success NUMERIC(5,4) NOT NULL DEFAULT 0,
    is_experiment BOOLEAN NOT NULL DEFAULT FALSE,
    based_on JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_candidates_version_id ON strategy_candidates(strategy_version_id);
