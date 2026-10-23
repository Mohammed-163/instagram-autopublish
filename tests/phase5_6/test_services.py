import uuid
import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL is not set — skipping live database tests."
)

from datetime import datetime
from database.repositories import (
    knowledge_rules_repository,
    decision_logs_repository,
    experiments_repository,
    hypotheses_repository,
    metrics_repository,
    memory_repository,
    quality_results_repository,
    notifications_repository,
    engine_health_repository,
    settings_repository,
    events_repository,
    failures_repository,
    posts_repository
)

def test_knowledge_service_create_and_transition(_migrated_database):
    rule = knowledge_rules_repository.create(
        name="test_rule",
        conditions={"key": "value"},
        action={"do": "something"}
    )
    assert rule.lifecycle_state == "proposed"
    knowledge_rules_repository.update(rule.id, lifecycle_state="active")
    rule = knowledge_rules_repository.get_by_id(rule.id)
    assert rule.lifecycle_state == "active"

def test_decision_service_log_and_query(_migrated_database):
    post_id = posts_repository.create().id
    log = decision_logs_repository.create(
        post_id=post_id,
        decision_type="topic_selection",
        engine_name="decision_engine",
        inputs={"options": ["a", "b"]},
        outputs={"selected": "a"},
        outcome="success"
    )
    assert log.decision_type == "topic_selection"
    assert log.post_id == post_id

def test_experiment_service_lifecycle(_migrated_database):
    hyp = hypotheses_repository.create(statement="Test statement")
    exp = experiments_repository.create(
        hypothesis_id=hyp.id,
        name="test_experiment"
    )
    assert exp.status == "planned"
    experiments_repository.update(exp.id, status="running")
    exp = experiments_repository.get_by_id(exp.id)
    assert exp.status == "running"

def test_metrics_service_snapshot_and_query(_migrated_database):
    post_id = posts_repository.create().id
    metrics_repository.upsert_snapshot(
        post_id=post_id,
        snapshot_period="24h",
        captured_at=datetime.utcnow(),
        views=100
    )
    # the repo does not have a fetch method, just asserting it doesn't crash

def test_memory_service_remember_recall(_migrated_database):
    mem = memory_repository.create(
        memory_key="test_key",
        memory_value={"data": "test"},
        importance=0.8
    )
    assert mem.memory_key == "test_key"

def test_quality_service_gate_checks(_migrated_database):
    post_id = posts_repository.create().id
    qr = quality_results_repository.create(
        post_id=post_id,
        gate_name="length_check",
        passed=True,
        score=0.9
    )
    assert qr.passed is True

def test_notification_service_lifecycle(_migrated_database):
    n = notifications_repository.create(
        channel="telegram",
        message_type="alert",
        recipient="user1",
        payload={"text": "hello"}
    )
    assert n.status == "pending"
    notifications_repository.update(n.id, status="sent")
    n = notifications_repository.get_by_id(n.id)
    assert n.status == "sent"

def test_engine_health_service_heartbeat(_migrated_database):
    engine_health_repository.report_heartbeat("decision_engine", "healthy")
    h = engine_health_repository.get_by_name("decision_engine")
    assert h.status == "healthy"

def test_settings_service_crud(_migrated_database):
    settings_repository.set("test_setting", "value")
    assert settings_repository.get("test_setting") == "value"
    settings_repository.delete("test_setting")
    assert settings_repository.get("test_setting") is None

def test_audit_service_events_and_failures(_migrated_database):
    e = events_repository.create(
        event_type="test_event",
        engine_name="test_engine"
    )
    assert e.event_type == "test_event"

    f = failures_repository.create(
        engine_name="test_engine",
        error_type="test_error",
        error_message="failed"
    )
    assert f.status == "open"
    failures_repository.update(f.id, status="resolved")
    f = failures_repository.get_by_id(f.id)
    assert f.status == "resolved"

def test_post_service_lifecycle(_migrated_database):
    p = posts_repository.create()
    assert p.status == "draft"
    posts_repository.update(p.id, status="ready")
    p = posts_repository.get_by_id(p.id)
    assert p.status == "ready"
