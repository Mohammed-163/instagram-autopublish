-- Phase 3 Part 2 Objective Layer

CREATE TABLE IF NOT EXISTS objective_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_name TEXT NOT NULL, -- e.g. Growth, Knowledge, Engagement, Retention, Balanced, Custom
    weights JSONB NOT NULL,
    version TEXT NOT NULL,
    settings_version TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS success_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    score NUMERIC(10,4) NOT NULL,
    explainability JSONB NOT NULL,
    objective_version TEXT NOT NULL,
    objective_profile TEXT NOT NULL,
    weight_config_version TEXT NOT NULL,
    settings_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
