-- Migration 0011: Decision Layer Foundation (Phase 5 Part 1)
-- Creates the minimum table required for DecisionCandidate persistence.
-- Explainability notes reuse the existing shared explainability_notes table
-- (subject_type = 'decision_candidate'); no new table needed for that.

CREATE TABLE IF NOT EXISTS decision_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_version_id UUID REFERENCES weekly_strategy_versions(id) ON DELETE SET NULL,
    strategy_candidate_id UUID REFERENCES strategy_candidates(id) ON DELETE SET NULL,

    decision_type TEXT NOT NULL,
    objective_profile TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Proposed'
        CHECK (status IN ('Proposed', 'Approved', 'Rejected')),

    confidence      NUMERIC(8, 4) NOT NULL DEFAULT 0,
    expected_gain   NUMERIC(8, 4) NOT NULL DEFAULT 0,
    risk            NUMERIC(8, 4) NOT NULL DEFAULT 0,
    decision_score  NUMERIC(8, 4) NOT NULL DEFAULT 0,

    related_opportunities JSONB NOT NULL DEFAULT '[]',
    explainability         JSONB NOT NULL DEFAULT '{}',
    versions                JSONB NOT NULL DEFAULT '{}',
    metadata                JSONB NOT NULL DEFAULT '{}',

    scoring_version       TEXT,
    fingerprint            TEXT,
    structural_fingerprint TEXT,
    feature_fingerprint    TEXT,
    fingerprint_hash       TEXT,
    fingerprint_version    TEXT,

    decided_reason TEXT,
    decided_by     TEXT,
    decided_at     TIMESTAMP WITH TIME ZONE,

    proposed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decision_candidates_status        ON decision_candidates (status);
CREATE INDEX IF NOT EXISTS idx_decision_candidates_strategy_ver  ON decision_candidates (strategy_version_id);
CREATE INDEX IF NOT EXISTS idx_decision_candidates_fingerprint   ON decision_candidates (fingerprint);
CREATE INDEX IF NOT EXISTS idx_decision_candidates_score         ON decision_candidates (decision_score DESC);
CREATE INDEX IF NOT EXISTS idx_decision_candidates_proposed_at   ON decision_candidates (proposed_at DESC);

-- -----------------------------------------------------------------------
-- Default scoring weights for DecisionScoringService. Read exclusively via
-- SettingsService (settings key "decision_scoring") — never hardcoded in
-- application code. Seeded here so the system works out of the box; can be
-- tuned later without a deploy.
-- -----------------------------------------------------------------------
INSERT INTO system_settings (key, value, description)
VALUES (
    'decision_scoring',
    '{
        "profiles": {
            "Balanced":     {"confidence_weight": 0.45, "gain_weight": 0.35, "risk_penalty_weight": 0.20},
            "Growth":       {"confidence_weight": 0.30, "gain_weight": 0.55, "risk_penalty_weight": 0.15},
            "Knowledge":    {"confidence_weight": 0.55, "gain_weight": 0.25, "risk_penalty_weight": 0.20},
            "Exploration":  {"confidence_weight": 0.25, "gain_weight": 0.45, "risk_penalty_weight": 0.30},
            "Conservative": {"confidence_weight": 0.50, "gain_weight": 0.20, "risk_penalty_weight": 0.30}
        }
    }'::jsonb,
    'DecisionScoringService weight profiles (Phase 5 Part 1) — Balanced/Growth/Knowledge/Exploration/Conservative'
)
ON CONFLICT (key) DO NOTHING;

-- Which profile Phase5DecisionEngine uses by default when evaluating a
-- completed weekly strategy. Read via SettingsService (key "decision_detection").
INSERT INTO system_settings (key, value, description)
VALUES (
    'decision_detection',
    '{"objective_profile": "Balanced", "scoring_profile": "Balanced"}'::jsonb,
    'Phase5DecisionEngine defaults (Phase 5 Part 1)'
)
ON CONFLICT (key) DO NOTHING;
