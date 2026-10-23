-- Phase 4 Part 2 -- Knowledge Coverage Engine Foundation

CREATE TABLE IF NOT EXISTS knowledge_coverage_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    knowledge_version TEXT,
    coverage_version TEXT,
    total_entities INTEGER NOT NULL DEFAULT 0,
    covered_entities INTEGER NOT NULL DEFAULT 0,
    unknown_entities INTEGER NOT NULL DEFAULT 0,
    knowledge_coverage NUMERIC(8,4) NOT NULL DEFAULT 0,
    knowledge_density NUMERIC(8,4) NOT NULL DEFAULT 0,
    exploration_ratio NUMERIC(8,4) NOT NULL DEFAULT 0,
    confidence_distribution JSONB NOT NULL,
    category_distribution JSONB NOT NULL,
    feature_distribution JSONB NOT NULL,
    notes JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kcs_calculated_at ON knowledge_coverage_snapshots(calculated_at);
