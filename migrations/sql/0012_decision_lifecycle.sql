-- Migration 0012: Decision Lifecycle Completion (Phase 5 Part 2)
-- Extends decision_candidates.status to the full lifecycle and adds the
-- decision_transitions history table (mirrors opportunity_transitions).

-- -----------------------------------------------------------------------
-- Extend allowed statuses: Proposed, Approved, Rejected (Part 1) plus
-- Scheduled, Executed, Cancelled, Expired (Part 2).
-- -----------------------------------------------------------------------
ALTER TABLE decision_candidates DROP CONSTRAINT IF EXISTS decision_candidates_status_check;

ALTER TABLE decision_candidates ADD CONSTRAINT decision_candidates_status_check
    CHECK (status IN (
        'Proposed', 'Approved', 'Rejected',
        'Scheduled', 'Executed', 'Cancelled', 'Expired'
    ));

-- -----------------------------------------------------------------------
-- Full transition history. Every lifecycle transition for a decision
-- candidate is recorded here, including the explainability snapshot and
-- versions in effect at the moment of the transition.
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_transitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_candidate_id UUID NOT NULL REFERENCES decision_candidates(id) ON DELETE CASCADE,

    previous_status TEXT,
    new_status      TEXT NOT NULL,
    transition_reason TEXT,
    actor              TEXT NOT NULL DEFAULT 'system',

    versions                JSONB NOT NULL DEFAULT '{}',
    explainability_snapshot JSONB NOT NULL DEFAULT '{}',

    transition_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decision_transitions_candidate ON decision_transitions (decision_candidate_id);
CREATE INDEX IF NOT EXISTS idx_decision_transitions_time      ON decision_transitions (transition_time DESC);
