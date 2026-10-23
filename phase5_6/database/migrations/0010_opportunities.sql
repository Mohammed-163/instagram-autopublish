-- Migration 0010: Opportunity Intelligence Layer (Phase C)
-- Creates opportunities table with full lifecycle support and transition log.

CREATE TABLE IF NOT EXISTS opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_opportunity_id UUID REFERENCES opportunities(id) ON DELETE SET NULL,
    opportunity_type TEXT NOT NULL,
    detector_name TEXT NOT NULL,
    detector_version TEXT NOT NULL DEFAULT '1.0.0',
    knowledge_version TEXT,
    coverage_version TEXT,
    scoring_version TEXT,
    settings_version TEXT,
    status TEXT NOT NULL DEFAULT 'Detected'
        CHECK (status IN (
            'Detected', 'Validated', 'Scheduled', 'Experimenting',
            'Succeeded', 'Failed', 'PromotedToKnowledge', 'Archived', 'Expired'
        )),
    confidence   NUMERIC(8, 4) NOT NULL DEFAULT 0,
    impact       NUMERIC(8, 4) NOT NULL DEFAULT 0,
    novelty      NUMERIC(8, 4) NOT NULL DEFAULT 0,
    knowledge_gap NUMERIC(8, 4) NOT NULL DEFAULT 0,
    risk         NUMERIC(8, 4) NOT NULL DEFAULT 0,
    opportunity_score NUMERIC(8, 4) NOT NULL DEFAULT 0,
    expected_gain NUMERIC(8, 4) NOT NULL DEFAULT 0,
    explainability JSONB NOT NULL DEFAULT '{}',
    evidence       JSONB NOT NULL DEFAULT '{}',
    related_entities JSONB NOT NULL DEFAULT '[]',
    metadata       JSONB NOT NULL DEFAULT '{}',
    fingerprint    TEXT,
    detected_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_opportunities_status    ON opportunities (status);
CREATE INDEX IF NOT EXISTS idx_opportunities_type      ON opportunities (opportunity_type);
CREATE INDEX IF NOT EXISTS idx_opportunities_detector  ON opportunities (detector_name);
CREATE INDEX IF NOT EXISTS idx_opportunities_score     ON opportunities (opportunity_score DESC);
CREATE INDEX IF NOT EXISTS idx_opportunities_fingerprint ON opportunities (fingerprint);
CREATE INDEX IF NOT EXISTS idx_opportunities_detected_at ON opportunities (detected_at DESC);

-- -----------------------------------------------------------------------
-- Lifecycle transition log
-- Every state change is recorded here with timestamp, reason, actor.
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS opportunity_transitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id UUID NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status   TEXT NOT NULL,
    reason      TEXT,
    actor       TEXT NOT NULL DEFAULT 'system',
    version     TEXT,
    transitioned_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_opp_transitions_opp_id ON opportunity_transitions (opportunity_id);
CREATE INDEX IF NOT EXISTS idx_opp_transitions_at     ON opportunity_transitions (transitioned_at DESC);
