-- Phase 3 Measurement Layer

CREATE TABLE IF NOT EXISTS metrics_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    metric_name TEXT NOT NULL,
    raw_value NUMERIC(16,4),
    normalized_value NUMERIC(16,4),
    measured_at TIMESTAMPTZ NOT NULL,
    interval_type TEXT NOT NULL,
    source TEXT NOT NULL,
    source_version TEXT,
    collector_version TEXT,
    normalization_version TEXT,
    confidence NUMERIC(4,3),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS feature_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    data_type TEXT,
    category TEXT,
    source TEXT,
    version TEXT,
    unit TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    introduced_at TIMESTAMPTZ DEFAULT now(),
    deprecated_at TIMESTAMPTZ,
    owner_engine TEXT,
    dependencies JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS features_lineage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    feature_name TEXT NOT NULL,
    value NUMERIC(16,4),
    lineage JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS data_quality_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID REFERENCES posts(id) ON DELETE CASCADE,
    metric_name TEXT,
    issue_type TEXT,
    description TEXT,
    severity TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reasoning_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id UUID REFERENCES reasoning_records(id) ON DELETE CASCADE,
    child_id UUID REFERENCES reasoning_records(id) ON DELETE CASCADE,
    node_type TEXT,
    context JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dataset_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version INTEGER NOT NULL UNIQUE,
    posts_count INTEGER,
    metrics_count INTEGER,
    features_count INTEGER,
    rules_count INTEGER,
    experiments_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
