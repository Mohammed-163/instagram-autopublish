"""
Smoke tests for the repository layer (both Phase 1 and the new Phase 2
foundation repositories), exercised through database.repositories.* exactly
as application code would use them — never raw SQL here.
"""
import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL is not set — skipping live database tests."
)

from datetime import datetime, timezone

from database.repositories import (
    confidence_scores_repository,
    engine_health_repository,
    events_repository,
    experiments_repository,
    features_repository,
    hypotheses_repository,
    knowledge_rules_repository,
    memory_repository,
    metrics_repository,
    posts_repository,
    quality_results_repository,
    scores_repository,
    settings_repository,
    topics_repository,
)


def test_posts_and_topics_repository_roundtrip(_migrated_database):
    topic = topics_repository.create(name="Quick Facts", slug="quick-facts")
    post = posts_repository.create(topic_id=topic.id, status="draft")

    fetched = posts_repository.get_by_id(post.id)
    assert fetched is not None
    assert fetched.topic_id == topic.id

    posts_repository.update(post.id, status="ready")
    assert posts_repository.get_by_id(post.id).status == "ready"


def test_metrics_upsert_is_idempotent_and_refreshes_topic_stats(_migrated_database):
    topic = topics_repository.create(name="Focus Tips", slug="focus-tips")
    post = posts_repository.create(topic_id=topic.id, status="published")

    metrics_repository.upsert_snapshot(post.id, "24h", datetime.now(timezone.utc), reach=1000, saves=42)
    metrics_repository.upsert_snapshot(post.id, "24h", datetime.now(timezone.utc), reach=1500, saves=50)

    snapshot = metrics_repository.get_snapshot(post.id, "24h")
    assert snapshot is not None
    assert snapshot.reach == 1500

    topics_repository.refresh_stats(topic.id)
    refreshed = topics_repository.get_by_id(topic.id)
    assert refreshed.posts_count == 1


def test_features_and_scores_repositories(_migrated_database):
    post = posts_repository.create(status="draft")

    features_repository.upsert_feature(post.id, "word_count", feature_value=18)
    features_repository.upsert_feature(post.id, "word_count", feature_value=21)
    feature = features_repository.get_feature(post.id, "word_count")
    assert feature is not None and int(feature.feature_value) == 21

    scores_repository.upsert_score(post.id, "overall_performance", 0.87, method_version="v1")
    score = scores_repository.get_score(post.id, "overall_performance", "v1")
    assert score is not None and float(score.score_value) == 0.87


def test_knowledge_rule_lifecycle_transition_writes_audit_event(_migrated_database):
    rule = knowledge_rules_repository.create(
        name="prefer_evening_posts", conditions={"hour_range": [18, 21]}, action={"boost_weight": 1.2}
    )
    assert rule.lifecycle_state == "proposed"

    updated = knowledge_rules_repository.transition_state(rule.id, "active", reason="passed validation")
    assert updated.lifecycle_state == "active"

    from database.repositories import rule_lifecycle_events_repository

    events = rule_lifecycle_events_repository.list_for_rule(rule.id)
    assert len(events) == 1
    assert events[0].from_state == "proposed"
    assert events[0].to_state == "active"


def test_hypothesis_and_experiment_repositories(_migrated_database):
    hypothesis = hypotheses_repository.create(statement="shorter hooks perform better", status="open")
    experiment = experiments_repository.create(hypothesis_id=hypothesis.id, name="hook_length_test", status="planned")

    assert experiments_repository.list_for_hypothesis(hypothesis.id) == [experiment]
    assert hypotheses_repository.list_by_status("open")[-1].id == hypothesis.id


def test_memory_repository_remember_and_recall(_migrated_database):
    memory_repository.remember("best_posting_window", {"start": "18:00", "end": "20:00"}, category="timing")
    entry = memory_repository.get_by_key("best_posting_window")
    assert entry is not None
    assert entry.memory_value["start"] == "18:00"

    memory_repository.remember("best_posting_window", {"start": "19:00", "end": "21:00"}, category="timing")
    assert memory_repository.get_by_key("best_posting_window").memory_value["start"] == "19:00"


def test_quality_results_and_confidence_scores(_migrated_database):
    post = posts_repository.create(status="draft")
    quality_results_repository.create(post_id=post.id, gate_name="length_check", passed=True, score=0.95)
    assert quality_results_repository.latest_passed(post.id, "length_check") is True

    confidence_scores_repository.create(subject_type="post", subject_id=post.id, score=0.6)
    latest = confidence_scores_repository.latest_for_subject("post", post.id)
    assert latest is not None and float(latest.score) == 0.6


def test_engine_health_heartbeat_and_events_log(_migrated_database):
    engine_health_repository.report_heartbeat("observation_engine", "healthy")
    health = engine_health_repository.get_by_name("observation_engine")
    assert health is not None and health.status == "healthy"

    events_repository.log("post.published", source="publish_script", payload={"post_id": "test"})
    recent = events_repository.list_by_type("post.published")
    assert len(recent) >= 1


def test_settings_repository_set_and_get(_migrated_database):
    settings_repository.set("min_confidence_to_auto_publish", 0.75, description="threshold used before Phase 2 exists")
    assert settings_repository.get("min_confidence_to_auto_publish") == 0.75
