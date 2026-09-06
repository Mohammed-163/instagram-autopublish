-- 0003_phase15_data_access_layer.sql

-- 1. Audit table
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name TEXT NOT NULL,
    record_id UUID NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    old_data JSONB,
    new_data JSONB,
    changed_by TEXT DEFAULT 'system',
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Database Views

CREATE OR REPLACE VIEW v_best_posts_last_30_days AS
SELECT 
    p.id as post_id,
    p.status,
    p.category,
    t.name as topic_name,
    m.reach,
    m.saves,
    m.engagement_rate,
    m.captured_at
FROM posts p
JOIN metrics m ON p.id = m.post_id
LEFT JOIN topics t ON p.topic_id = t.id
WHERE p.status = 'published' 
  AND m.captured_at >= (now() - interval '30 days')
ORDER BY m.engagement_rate DESC NULLS LAST;

CREATE OR REPLACE VIEW v_weekly_category_statistics AS
SELECT 
    date_trunc('week', p.published_at) as week,
    t.name as topic_name,
    count(p.id) as post_count,
    avg(m.reach) as avg_reach,
    avg(m.saves) as avg_saves,
    avg(m.engagement_rate) as avg_engagement_rate
FROM posts p
JOIN metrics m ON p.id = m.post_id
LEFT JOIN topics t ON p.topic_id = t.id
WHERE p.status = 'published' AND p.published_at IS NOT NULL
GROUP BY date_trunc('week', p.published_at), t.name;

CREATE OR REPLACE VIEW v_top_hooks AS
SELECT 
    split_part(p.final_text, E'\n', 1) as hook,
    count(p.id) as usage_count,
    avg(m.engagement_rate) as avg_engagement_rate
FROM posts p
JOIN metrics m ON p.id = m.post_id
WHERE p.status = 'published' AND p.final_text IS NOT NULL
GROUP BY split_part(p.final_text, E'\n', 1)
ORDER BY avg_engagement_rate DESC NULLS LAST;

CREATE OR REPLACE VIEW v_top_backgrounds AS
SELECT 
    d.background_type,
    count(p.id) as usage_count,
    avg(m.engagement_rate) as avg_engagement_rate
FROM designs d
JOIN posts p ON d.post_id = p.id
JOIN metrics m ON p.id = m.post_id
WHERE p.status = 'published'
GROUP BY d.background_type
ORDER BY avg_engagement_rate DESC NULLS LAST;

CREATE OR REPLACE VIEW v_failed_posts AS
SELECT 
    p.id as post_id,
    -- Assume error details could be derived from failures or posts if it has an error column
    p.status,
    f.failure_type,
    f.occurred_at
FROM posts p
LEFT JOIN failures f ON f.source = 'post_' || p.id::text
WHERE p.status = 'failed';

CREATE OR REPLACE VIEW v_experiment_summary AS
SELECT 
    e.status,
    h.status as hypothesis_status,
    count(e.id) as experiment_count
FROM intelligence_experiments e
JOIN hypotheses h ON e.hypothesis_id = h.id
GROUP BY e.status, h.status;

CREATE OR REPLACE VIEW v_knowledge_statistics AS
SELECT 
    lifecycle_state,
    count(id) as rule_count,
    avg(confidence) as avg_confidence,
    avg(evidence_count) as avg_evidence
FROM knowledge_rules
GROUP BY lifecycle_state;

CREATE OR REPLACE VIEW v_decision_statistics AS
SELECT 
    decision_type,
    count(id) as decision_count,
    avg(confidence) as avg_confidence
FROM decision_logs
GROUP BY decision_type;

CREATE OR REPLACE VIEW v_notification_statistics AS
SELECT 
    channel,
    severity,
    status,
    count(id) as notification_count
FROM notifications
GROUP BY channel, severity, status;

CREATE OR REPLACE VIEW v_engine_health_summary AS
SELECT 
    engine_name,
    status
    -- last_run_at -- Note: Add here if such column exists in engine_health, skipped assuming basic schema
FROM engine_health
ORDER BY engine_name;

CREATE OR REPLACE VIEW v_quality_gate_summary AS
SELECT 
    gate_name,
    count(id) as total_checks,
    sum(case when passed then 1 else 0 end)::numeric / count(id) as pass_rate
FROM quality_results
GROUP BY gate_name;

CREATE OR REPLACE VIEW v_memory_summary AS
SELECT 
    category,
    count(id) as memory_count,
    avg(importance) as avg_importance
FROM memory_entries
GROUP BY category;

CREATE OR REPLACE VIEW v_weekly_plan_performance AS
SELECT 
    wp.week_start_date,
    wp.status
FROM weekly_plans wp
ORDER BY wp.week_start_date DESC;

-- 3. Materialized Views

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_post_performance_30d AS
SELECT 
    p.id as post_id,
    p.status,
    p.category,
    t.name as topic_name,
    m.reach,
    m.saves,
    m.engagement_rate,
    m.captured_at
FROM posts p
JOIN metrics m ON p.id = m.post_id
LEFT JOIN topics t ON p.topic_id = t.id
WHERE p.status = 'published' 
  AND m.captured_at >= (now() - interval '30 days');

CREATE UNIQUE INDEX idx_mv_post_perf_30d_post_id ON mv_post_performance_30d(post_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_topic_ranking AS
SELECT 
    t.id as topic_id,
    t.name as topic_name,
    count(p.id) as total_posts,
    avg(m.engagement_rate) as avg_engagement_rate
FROM topics t
JOIN posts p ON p.topic_id = t.id
JOIN metrics m ON p.id = m.post_id
WHERE p.status = 'published'
GROUP BY t.id, t.name;

CREATE UNIQUE INDEX idx_mv_topic_ranking_topic_id ON mv_topic_ranking(topic_id);

-- 4. Stored Functions

CREATE OR REPLACE FUNCTION calculate_post_score(p_post_id UUID)
RETURNS NUMERIC AS $$
DECLARE
    v_reach BIGINT;
    v_saves BIGINT;
    v_engagement_rate NUMERIC;
    v_score NUMERIC := 0;
BEGIN
    SELECT reach, saves, engagement_rate 
    INTO v_reach, v_saves, v_engagement_rate
    FROM metrics
    WHERE post_id = p_post_id
    ORDER BY captured_at DESC
    LIMIT 1;
    
    IF v_reach IS NOT NULL THEN
        -- Standardized score components
        v_score := (COALESCE(v_reach, 0) * 0.1) + (COALESCE(v_saves, 0) * 0.3) + (COALESCE(v_engagement_rate, 0) * 100 * 0.6);
    END IF;
    
    RETURN v_score;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION calculate_confidence(p_subject_type TEXT, p_subject_id UUID)
RETURNS NUMERIC AS $$
DECLARE
    v_evidence_count INTEGER;
    v_base_confidence NUMERIC := 0.1;
    v_calculated NUMERIC;
BEGIN
    IF p_subject_type = 'knowledge_rule' THEN
        SELECT evidence_count INTO v_evidence_count
        FROM knowledge_rules
        WHERE id = p_subject_id;
        
        IF v_evidence_count IS NOT NULL AND v_evidence_count > 0 THEN
            v_calculated := LEAST(0.99, v_base_confidence + (ln(v_evidence_count + 1) * 0.1));
        ELSE
            v_calculated := v_base_confidence;
        END IF;
    ELSE
        v_calculated := v_base_confidence;
    END IF;
    
    RETURN v_calculated;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION create_weekly_snapshot(p_week_start DATE)
RETURNS UUID AS $$
DECLARE
    v_snapshot_id UUID;
BEGIN
    v_snapshot_id := gen_random_uuid();
    INSERT INTO event_logs (id, event_type, source, occurred_at)
    VALUES (v_snapshot_id, 'weekly_snapshot_created', 'system', now());
    RETURN v_snapshot_id;
END;
$$ LANGUAGE plpgsql VOLATILE;

CREATE OR REPLACE FUNCTION activate_rule(p_rule_id UUID, p_reason TEXT DEFAULT NULL)
RETURNS UUID AS $$
DECLARE
    v_event_id UUID;
    v_old_state TEXT;
BEGIN
    SELECT lifecycle_state INTO v_old_state FROM knowledge_rules WHERE id = p_rule_id;
    
    UPDATE knowledge_rules 
    SET lifecycle_state = 'active'
    WHERE id = p_rule_id;
    
    v_event_id := gen_random_uuid();
    INSERT INTO rule_lifecycle_events (id, rule_id, from_state, to_state)
    VALUES (v_event_id, p_rule_id, v_old_state, 'active');
    
    RETURN v_event_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION archive_rule(p_rule_id UUID, p_reason TEXT DEFAULT NULL)
RETURNS UUID AS $$
DECLARE
    v_event_id UUID;
    v_old_state TEXT;
BEGIN
    SELECT lifecycle_state INTO v_old_state FROM knowledge_rules WHERE id = p_rule_id;
    
    UPDATE knowledge_rules 
    SET lifecycle_state = 'retired'
    WHERE id = p_rule_id;
    
    v_event_id := gen_random_uuid();
    INSERT INTO rule_lifecycle_events (id, rule_id, from_state, to_state)
    VALUES (v_event_id, p_rule_id, v_old_state, 'retired');
    
    RETURN v_event_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION deprecate_rule(p_rule_id UUID, p_reason TEXT DEFAULT NULL)
RETURNS UUID AS $$
DECLARE
    v_event_id UUID;
    v_old_state TEXT;
BEGIN
    SELECT lifecycle_state INTO v_old_state FROM knowledge_rules WHERE id = p_rule_id;
    
    UPDATE knowledge_rules 
    SET lifecycle_state = 'suspended'
    WHERE id = p_rule_id;
    
    v_event_id := gen_random_uuid();
    INSERT INTO rule_lifecycle_events (id, rule_id, from_state, to_state)
    VALUES (v_event_id, p_rule_id, v_old_state, 'suspended');
    
    RETURN v_event_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION promote_candidate_rule(p_rule_id UUID, p_reason TEXT DEFAULT NULL)
RETURNS UUID AS $$
DECLARE
    v_event_id UUID;
    v_old_state TEXT;
BEGIN
    SELECT lifecycle_state INTO v_old_state FROM knowledge_rules WHERE id = p_rule_id;
    
    IF v_old_state != 'proposed' THEN
        RAISE EXCEPTION 'Rule must be in proposed state to be promoted.';
    END IF;
    
    UPDATE knowledge_rules 
    SET lifecycle_state = 'active'
    WHERE id = p_rule_id;
    
    v_event_id := gen_random_uuid();
    INSERT INTO rule_lifecycle_events (id, rule_id, from_state, to_state)
    VALUES (v_event_id, p_rule_id, v_old_state, 'active');
    
    RETURN v_event_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION refresh_learning_views()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_post_performance_30d;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_topic_ranking;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION cleanup_old_data(p_days_to_keep INTEGER DEFAULT 90)
RETURNS TABLE(table_name TEXT, deleted_count BIGINT) AS $$
DECLARE
    v_count BIGINT;
BEGIN
    DELETE FROM event_logs WHERE occurred_at < (now() - (p_days_to_keep || ' days')::interval);
    GET DIAGNOSTICS v_count = ROW_COUNT;
    table_name := 'event_logs';
    deleted_count := v_count;
    RETURN NEXT;
    
    DELETE FROM audit_log WHERE changed_at < (now() - (p_days_to_keep || ' days')::interval);
    GET DIAGNOSTICS v_count = ROW_COUNT;
    table_name := 'audit_log';
    deleted_count := v_count;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- 5. Audit Triggers

CREATE OR REPLACE FUNCTION generic_audit_trigger_function()
RETURNS TRIGGER AS $$
DECLARE
    v_old_data JSONB;
    v_new_data JSONB;
    v_record_id UUID;
BEGIN
    IF (TG_OP = 'DELETE') THEN
        v_old_data := to_jsonb(OLD);
        IF v_old_data ? 'id' THEN
            v_record_id := (v_old_data->>'id')::UUID;
        ELSE
            v_record_id := gen_random_uuid(); 
        END IF;
        
        INSERT INTO audit_log (table_name, record_id, action, old_data)
        VALUES (TG_TABLE_NAME::TEXT, v_record_id, TG_OP, v_old_data);
        RETURN OLD;
    ELSIF (TG_OP = 'UPDATE') THEN
        v_old_data := to_jsonb(OLD);
        v_new_data := to_jsonb(NEW);
        IF v_new_data ? 'id' THEN
            v_record_id := (v_new_data->>'id')::UUID;
        ELSE
            v_record_id := gen_random_uuid();
        END IF;

        INSERT INTO audit_log (table_name, record_id, action, old_data, new_data)
        VALUES (TG_TABLE_NAME::TEXT, v_record_id, TG_OP, v_old_data, v_new_data);
        RETURN NEW;
    ELSIF (TG_OP = 'INSERT') THEN
        v_new_data := to_jsonb(NEW);
        IF v_new_data ? 'id' THEN
            v_record_id := (v_new_data->>'id')::UUID;
        ELSE
            v_record_id := gen_random_uuid();
        END IF;

        INSERT INTO audit_log (table_name, record_id, action, new_data)
        VALUES (TG_TABLE_NAME::TEXT, v_record_id, TG_OP, v_new_data);
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DO $$ 
DECLARE
    t text;
BEGIN
    FOR t IN 
        SELECT unnest(ARRAY['knowledge_rules', 'weekly_plans', 'strategy_history', 'prompt_versions', 'model_versions'])
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_audit_%I ON %I', t, t);
        EXECUTE format('CREATE TRIGGER trg_audit_%I AFTER INSERT OR UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION generic_audit_trigger_function()', t, t);
    END LOOP;
END;
$$;

-- 6. Additional Indexes

CREATE INDEX IF NOT EXISTS idx_posts_status_published_at ON posts (status, published_at) WHERE status = 'published';
CREATE INDEX IF NOT EXISTS idx_metrics_captured_at_period ON metrics (captured_at, snapshot_period);
CREATE INDEX IF NOT EXISTS idx_knowledge_rules_state_confidence ON knowledge_rules (lifecycle_state, confidence) WHERE lifecycle_state = 'active';
CREATE INDEX IF NOT EXISTS idx_decision_logs_created_at ON decision_logs (created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications (created_at);
CREATE INDEX IF NOT EXISTS idx_event_logs_source ON event_logs (source);
CREATE INDEX IF NOT EXISTS idx_audit_log_table ON audit_log (table_name, changed_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_record ON audit_log (record_id);
CREATE INDEX IF NOT EXISTS idx_failures_occurred_at ON failures (occurred_at);
CREATE INDEX IF NOT EXISTS idx_confidence_scores_computed_at ON confidence_scores (computed_at);
CREATE INDEX IF NOT EXISTS idx_scores_computed_at ON scores (computed_at);
CREATE INDEX IF NOT EXISTS idx_features_extracted_at ON features (extracted_at);
CREATE INDEX IF NOT EXISTS idx_experiments_started_at ON intelligence_experiments (started_at);
CREATE INDEX IF NOT EXISTS idx_weekly_plans_week_start ON weekly_plans (week_start_date);
CREATE INDEX IF NOT EXISTS idx_quality_results_checked_at ON quality_results (checked_at);

CREATE INDEX IF NOT EXISTS idx_knowledge_rules_conditions_gin ON knowledge_rules USING gin (conditions);
CREATE INDEX IF NOT EXISTS idx_knowledge_rules_action_gin ON knowledge_rules USING gin (action);
CREATE INDEX IF NOT EXISTS idx_memory_entries_value_gin ON memory_entries USING gin (memory_value);

-- 7. Additional Triggers

CREATE OR REPLACE FUNCTION validate_experiment_status_transition()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = 'completed' OR OLD.status = 'failed' THEN
        IF NEW.status != OLD.status THEN
            RAISE EXCEPTION 'Cannot change status of a completed or failed experiment.';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_experiment_status ON intelligence_experiments;
CREATE TRIGGER trg_validate_experiment_status
BEFORE UPDATE OF status ON intelligence_experiments
FOR EACH ROW EXECUTE FUNCTION validate_experiment_status_transition();

CREATE OR REPLACE FUNCTION validate_knowledge_rule_lifecycle()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.lifecycle_state = 'retired' AND NEW.lifecycle_state != 'retired' THEN
        RAISE EXCEPTION 'Cannot change state of a retired rule.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_knowledge_rule_lifecycle ON knowledge_rules;
CREATE TRIGGER trg_validate_knowledge_rule_lifecycle
BEFORE UPDATE OF lifecycle_state ON knowledge_rules
FOR EACH ROW EXECUTE FUNCTION validate_knowledge_rule_lifecycle();
