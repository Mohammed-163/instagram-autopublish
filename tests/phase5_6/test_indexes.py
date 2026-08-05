"""Verifies the expected indexes actually exist after migration."""
from __future__ import annotations

from sqlalchemy import text

EXPECTED_INDEXES = {
    # Phase 1
    "idx_posts_status", "idx_posts_scheduled_at", "idx_posts_topic_id",
    "idx_posts_instagram_media_id", "idx_designs_post_id", "idx_media_post_id",
    "idx_publishing_schedule_status_time", "idx_publishing_schedule_post_id",
    "idx_publishing_history_post_id", "idx_publishing_history_result",
    "idx_metrics_post_id_period", "idx_metrics_captured_at",
    # Phase 2 foundation
    "idx_features_post_id", "idx_features_key",
    "idx_scores_post_id", "idx_scores_type",
    "idx_knowledge_rules_state", "idx_knowledge_rules_version",
    "idx_rule_lifecycle_events_rule_id",
    "idx_hypotheses_status",
    "idx_experiments_hypothesis_id", "idx_experiments_status",
    "idx_memory_entries_category",
    "idx_weekly_plans_status",
    "idx_strategy_history_name",
    "idx_decision_logs_type", "idx_decision_logs_post_id",
    "idx_confidence_scores_subject",
    "idx_quality_results_post_id", "idx_quality_results_gate",
    "idx_notifications_status",
    "idx_event_logs_type", "idx_event_logs_occurred_at",
    "idx_prompt_versions_name",
    "idx_model_versions_purpose",
    "idx_failures_source", "idx_failures_resolved",
    "idx_explainability_notes_subject",
    # Phase 1.5 Additional Indexes
    "idx_posts_status_published_at", "idx_metrics_captured_at_period",
    "idx_knowledge_rules_state_confidence", "idx_decision_logs_created_at",
    "idx_notifications_created_at", "idx_event_logs_source",
    "idx_audit_log_table", "idx_audit_log_record",
    "idx_failures_occurred_at", "idx_confidence_scores_computed_at",
    "idx_scores_computed_at", "idx_features_extracted_at",
    "idx_experiments_started_at", "idx_weekly_plans_week_start",
    "idx_quality_results_checked_at", "idx_knowledge_rules_conditions_gin",
    "idx_knowledge_rules_action_gin", "idx_memory_entries_value_gin",
    "idx_mv_post_perf_30d_post_id", "idx_mv_topic_ranking_topic_id",
}


def test_all_expected_indexes_exist(engine, _migrated_database):
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"))
        actual = {row[0] for row in rows}

    missing = EXPECTED_INDEXES - actual
    assert not missing, f"Missing indexes after migration: {sorted(missing)}"
