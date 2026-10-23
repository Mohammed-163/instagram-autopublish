-- Migration 0013: Execution Layer Foundation (Phase 6 Part 1)
-- Creates execution_records and execution_transitions tables.
-- No real execution logic lives here — this is the persistence foundation only.
--
-- Allowed lifecycle states:
--   Pending → Scheduled → Running → Completed
--                                 → Failed
--   Pending → Cancelled
--   Scheduled → Cancelled
--   Pending → Expired
--   Scheduled → Expired
--
-- Any other transition is rejected by ExecutionValidationService.

CREATE TABLE IF NOT EXISTS execution_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source decision that triggered this execution
    decision_candidate_id UUID REFERENCES decision_candidates(id) ON DELETE SET NULL,

    -- Lifecycle status (7 allowed states)
    status TEXT NOT NULL DEFAULT 'Pending'
        CHECK (status IN (
            'Pending',
            'Scheduled',
            'Running',
            'Completed',
            'Failed',
            'Cancelled',
            'Expired'
        )),

    -- What is being executed (mirrors decision type / profile for traceability)
    execution_type    TEXT NOT NULL,
    objective_profile TEXT NOT NULL DEFAULT '',

    -- Deterministic replay / deduplication
    fingerprint         TEXT,
    fingerprint_version TEXT,

    -- Rich context forwarded from the approved decision
    metadata_      JSONB NOT NULL DEFAULT '{}',
    versions       JSONB NOT NULL DEFAULT '{}',
    explainability JSONB NOT NULL DEFAULT '{}',

    -- Outcome details (populated on completion / failure)
    result         JSONB NOT NULL DEFAULT '{}',
    failure_reason TEXT,

    -- Timing
    scheduled_at TIMESTAMP WITH TIME ZONE,
    started_at   TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    expired_at   TIMESTAMP WITH TIME ZONE,
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_execution_records_status              ON execution_records (status);
CREATE INDEX IF NOT EXISTS idx_execution_records_decision_candidate  ON execution_records (decision_candidate_id);
CREATE INDEX IF NOT EXISTS idx_execution_records_fingerprint         ON execution_records (fingerprint);
CREATE INDEX IF NOT EXISTS idx_execution_records_created_at          ON execution_records (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_records_execution_type      ON execution_records (execution_type);

-- ---------------------------------------------------------------------------
-- Execution transition history — every status change is written here so the
-- full lifecycle is auditable and deterministically replayable.
-- Explainability fields: reason, versions, timestamp, actor are all required.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS execution_transitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    execution_id UUID NOT NULL REFERENCES execution_records(id) ON DELETE CASCADE,

    from_status TEXT,            -- NULL for the initial Pending transition
    to_status   TEXT NOT NULL,
    reason      TEXT NOT NULL DEFAULT '',
    actor       TEXT NOT NULL DEFAULT 'system',

    -- Explainability
    versions    JSONB NOT NULL DEFAULT '{}',

    transitioned_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_execution_transitions_execution_id    ON execution_transitions (execution_id);
CREATE INDEX IF NOT EXISTS idx_execution_transitions_transitioned_at ON execution_transitions (transitioned_at DESC);
