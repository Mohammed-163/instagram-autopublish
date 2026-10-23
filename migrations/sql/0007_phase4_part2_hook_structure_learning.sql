-- Phase 4 Part 2 -- Hook Structure Learning & Opportunity Discovery Foundation
-- (Opportunity Discovery itself is NOT built here; only the foundation
--  table hook_feature_statistics is created so that phase needs no
--  further migration.)

CREATE TABLE IF NOT EXISTS hook_structures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    category TEXT,
    hook_type TEXT,
    hook_text TEXT NOT NULL,
    features JSONB NOT NULL,
    explainability JSONB NOT NULL,
    grammar_sequence JSONB NOT NULL,
    analyzer_versions JSONB NOT NULL,
    schema_version TEXT NOT NULL DEFAULT '1.0.0',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hook_structures_post_id ON hook_structures(post_id);
CREATE INDEX IF NOT EXISTS idx_hook_structures_category_hook_type ON hook_structures(category, hook_type);

CREATE TABLE IF NOT EXISTS hook_feature_values (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hook_structure_id UUID NOT NULL REFERENCES hook_structures(id) ON DELETE CASCADE,
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    feature_name TEXT NOT NULL,
    feature_value JSONB NOT NULL,
    extraction_method TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'hook_text',
    analyzer_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hook_feature_values_structure_id ON hook_feature_values(hook_structure_id);
CREATE INDEX IF NOT EXISTS idx_hook_feature_values_feature_name ON hook_feature_values(feature_name);

CREATE TABLE IF NOT EXISTS hook_feature_statistics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category TEXT NOT NULL,
    hook_type TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    sample_size INTEGER NOT NULL DEFAULT 0,
    contribution_sum NUMERIC(12,4) NOT NULL DEFAULT 0,
    avg_contribution NUMERIC(8,4) NOT NULL DEFAULT 0,
    confidence NUMERIC(5,4) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_hook_feature_statistics_category_hook_type_feature UNIQUE (category, hook_type, feature_name)
);

CREATE INDEX IF NOT EXISTS idx_hook_feature_statistics_category_hook_type ON hook_feature_statistics(category, hook_type);
