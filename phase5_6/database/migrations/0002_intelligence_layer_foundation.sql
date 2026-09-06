-- =============================================================================
-- 0002_intelligence_layer_foundation.sql
-- =============================================================================
-- Adds the structural foundation required by the future Learning &
-- Intelligence Layer (Phase 2): features, scores, knowledge, experiments,
-- memory, planning, decisions, confidence, quality gate, engine health,
-- notifications, an event backbone, and versioned config/prompts/models.
--
-- No Phase 2 engine code runs yet. These tables exist purely so Phase 2 can
-- be built without a schema redesign. Nothing writes to them yet except
-- where a Phase 1 script is explicitly wired to (see repositories).
--
-- "Categories" from the project charter are intentionally NOT a new table
-- here: the existing `topics` table already is the category dimension
-- (name/slug/weight/rollup stats) since version 1. Adding a duplicate
-- `categories` table would just be two sources of truth for the same
-- concept.
-- =============================================================================

-- Ensure the trigger helper exists even when an existing database was marked
-- as having the baseline applied without successfully installing functions.sql.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- features — generic per-post extracted feature store (key/value)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS features (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id             UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    feature_key         TEXT NOT NULL,
    feature_value       NUMERIC(18, 6),
    feature_value_text  TEXT,
    source              TEXT,
    extracted_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (post_id, feature_key)
);

-- -----------------------------------------------------------------------------
-- scores — generic per-post computed scores (several scoring methods coexist)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scores (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id             UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    score_type          TEXT NOT NULL,
    score_value         NUMERIC(10, 4) NOT NULL,
    method_version      TEXT,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (post_id, score_type, method_version)
);

-- -----------------------------------------------------------------------------
-- intelligence_knowledge_versions — immutable snapshot markers of "what the system believed"
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS intelligence_knowledge_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_number      INTEGER NOT NULL UNIQUE,
    summary             TEXT,
    is_active           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- knowledge_rules — executable rules produced by the learning loop
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge_rules (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_version_id    UUID REFERENCES intelligence_knowledge_versions(id) ON DELETE SET NULL,
    name                    TEXT NOT NULL,
    conditions              JSONB NOT NULL,
    action                  JSONB NOT NULL,
    weight                  NUMERIC(10, 4) NOT NULL DEFAULT 1.0,
    confidence              NUMERIC(5, 4),
    evidence_count          INTEGER NOT NULL DEFAULT 0,
    lifecycle_state         TEXT NOT NULL DEFAULT 'proposed'
                                CHECK (lifecycle_state IN ('proposed', 'active', 'suspended', 'retired')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- rule_lifecycle_events — audit trail of every state change of a knowledge_rule
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rule_lifecycle_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id             UUID NOT NULL REFERENCES knowledge_rules(id) ON DELETE CASCADE,
    from_state          TEXT,
    to_state            TEXT NOT NULL,
    reason              TEXT,
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- hypotheses — candidate beliefs awaiting experimental validation
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hypotheses (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    statement           TEXT NOT NULL,
    rationale           TEXT,
    status              TEXT NOT NULL DEFAULT 'open'
                            CHECK (status IN ('open', 'testing', 'confirmed', 'rejected', 'inconclusive')),
    confidence          NUMERIC(5, 4),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    evaluated_at        TIMESTAMPTZ
);

-- -----------------------------------------------------------------------------
-- experiments — concrete, run-able tests of a hypothesis
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS intelligence_experiments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id       UUID NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    variant_config      JSONB,
    status              TEXT NOT NULL DEFAULT 'planned'
                            CHECK (status IN ('planned', 'running', 'completed', 'aborted')),
    started_at          TIMESTAMPTZ,
    ended_at            TIMESTAMPTZ,
    result_summary      TEXT,
    result_data         JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- memory_entries — long-lived key/value knowledge recalled across cycles
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS memory_entries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_key          TEXT NOT NULL UNIQUE,
    memory_value        JSONB NOT NULL,
    category            TEXT,
    importance          NUMERIC(5, 4) NOT NULL DEFAULT 0.5,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- weekly_plans — the strategic plan produced at the start of each week
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weekly_plans (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    week_start_date     DATE NOT NULL UNIQUE,
    week_end_date       DATE NOT NULL,
    plan                JSONB NOT NULL,
    status              TEXT NOT NULL DEFAULT 'draft'
                            CHECK (status IN ('draft', 'active', 'completed', 'superseded')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- strategy_history — every change to overall strategy, before/after + why
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_history (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name       TEXT NOT NULL,
    changed_from        JSONB,
    changed_to          JSONB NOT NULL,
    reason              TEXT,
    effective_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- decision_logs — every autonomous decision, with context + reasoning
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_type       TEXT NOT NULL,
    related_post_id     UUID REFERENCES posts(id) ON DELETE SET NULL,
    context             JSONB,
    chosen_action       JSONB,
    reasoning           TEXT,
    confidence          NUMERIC(5, 4),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- confidence_scores — generic confidence score for any subject
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS confidence_scores (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_type        TEXT NOT NULL,
    subject_id          UUID NOT NULL,
    score               NUMERIC(5, 4) NOT NULL,
    method              TEXT,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- quality_results — Quality Gate outcomes for candidate posts before publish
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quality_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id             UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    gate_name           TEXT NOT NULL,
    passed              BOOLEAN NOT NULL,
    score               NUMERIC(6, 3),
    details             JSONB,
    checked_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- engine_health — heartbeat/status of every autonomous engine
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS engine_health (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    engine_name         TEXT NOT NULL UNIQUE,
    status              TEXT NOT NULL DEFAULT 'unknown'
                            CHECK (status IN ('unknown', 'healthy', 'degraded', 'down')),
    last_run_at         TIMESTAMPTZ,
    last_success_at     TIMESTAMPTZ,
    last_error          TEXT,
    metadata            JSONB,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- notifications — outbound notification log (Telegram today, others later)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel             TEXT NOT NULL,
    severity            TEXT NOT NULL DEFAULT 'info'
                            CHECK (severity IN ('info', 'warning', 'critical')),
    title               TEXT,
    message             TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'sent', 'failed')),
    metadata            JSONB,
    sent_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- event_logs — append-only backbone for the Event-Driven engines of Phase 2
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type          TEXT NOT NULL,
    source              TEXT NOT NULL,
    payload             JSONB,
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- system_settings — generic key/value config store (flags, thresholds)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_settings (
    key                 TEXT PRIMARY KEY,
    value               JSONB NOT NULL,
    description         TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- prompt_versions — every prompt template used to generate content, versioned
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prompt_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    version             TEXT NOT NULL,
    template            TEXT NOT NULL,
    variables           JSONB,
    is_active           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);

-- -----------------------------------------------------------------------------
-- model_versions — every AI model/provider version used in the pipeline
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider            TEXT NOT NULL,
    model_name          TEXT NOT NULL,
    version             TEXT,
    purpose             TEXT,
    is_active           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, model_name, version)
);

-- -----------------------------------------------------------------------------
-- failures — structured failure log for any part of the system
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS failures (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source              TEXT NOT NULL,
    failure_type        TEXT NOT NULL,
    message             TEXT NOT NULL,
    context             JSONB,
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved            BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at         TIMESTAMPTZ
);

-- -----------------------------------------------------------------------------
-- explainability_notes — human-readable "why" for any subject
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS explainability_notes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_type        TEXT NOT NULL,
    subject_id          UUID NOT NULL,
    explanation         TEXT NOT NULL,
    factors             JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- indexes
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_features_post_id                 ON features (post_id);
CREATE INDEX IF NOT EXISTS idx_features_key                     ON features (feature_key);

CREATE INDEX IF NOT EXISTS idx_scores_post_id                   ON scores (post_id);
CREATE INDEX IF NOT EXISTS idx_scores_type                      ON scores (score_type);

CREATE INDEX IF NOT EXISTS idx_knowledge_rules_state             ON knowledge_rules (lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_knowledge_rules_version            ON knowledge_rules (knowledge_version_id);

CREATE INDEX IF NOT EXISTS idx_rule_lifecycle_events_rule_id      ON rule_lifecycle_events (rule_id);

CREATE INDEX IF NOT EXISTS idx_hypotheses_status                  ON hypotheses (status);

CREATE INDEX IF NOT EXISTS idx_experiments_hypothesis_id           ON intelligence_experiments (hypothesis_id);
CREATE INDEX IF NOT EXISTS idx_experiments_status                  ON intelligence_experiments (status);

CREATE INDEX IF NOT EXISTS idx_memory_entries_category              ON memory_entries (category);

CREATE INDEX IF NOT EXISTS idx_weekly_plans_status                  ON weekly_plans (status);

CREATE INDEX IF NOT EXISTS idx_strategy_history_name                ON strategy_history (strategy_name);

CREATE INDEX IF NOT EXISTS idx_decision_logs_type                   ON decision_logs (decision_type);
CREATE INDEX IF NOT EXISTS idx_decision_logs_post_id                ON decision_logs (related_post_id);

CREATE INDEX IF NOT EXISTS idx_confidence_scores_subject             ON confidence_scores (subject_type, subject_id);

CREATE INDEX IF NOT EXISTS idx_quality_results_post_id                ON quality_results (post_id);
CREATE INDEX IF NOT EXISTS idx_quality_results_gate                   ON quality_results (gate_name);

CREATE INDEX IF NOT EXISTS idx_notifications_status                    ON notifications (status);

CREATE INDEX IF NOT EXISTS idx_event_logs_type                          ON event_logs (event_type);
CREATE INDEX IF NOT EXISTS idx_event_logs_occurred_at                    ON event_logs (occurred_at);

CREATE INDEX IF NOT EXISTS idx_prompt_versions_name                       ON prompt_versions (name);

CREATE INDEX IF NOT EXISTS idx_model_versions_purpose                      ON model_versions (purpose);

CREATE INDEX IF NOT EXISTS idx_failures_source                             ON failures (source);
CREATE INDEX IF NOT EXISTS idx_failures_resolved                            ON failures (resolved);

CREATE INDEX IF NOT EXISTS idx_explainability_notes_subject                  ON explainability_notes (subject_type, subject_id);

-- =============================================================================
-- triggers — keep updated_at current on the new mutable tables
-- (reuses set_updated_at() from functions.sql, applied in version 1)
-- =============================================================================
DROP TRIGGER IF EXISTS trg_knowledge_rules_set_updated_at ON knowledge_rules;
CREATE TRIGGER trg_knowledge_rules_set_updated_at
    BEFORE UPDATE ON knowledge_rules
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_memory_entries_set_updated_at ON memory_entries;
CREATE TRIGGER trg_memory_entries_set_updated_at
    BEFORE UPDATE ON memory_entries
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_engine_health_set_updated_at ON engine_health;
CREATE TRIGGER trg_engine_health_set_updated_at
    BEFORE UPDATE ON engine_health
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_system_settings_set_updated_at ON system_settings;
CREATE TRIGGER trg_system_settings_set_updated_at
    BEFORE UPDATE ON system_settings
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
