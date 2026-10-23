"""
Tests for ExperimentEngine.
Engine now receives ExperimentService instead of experiments_repository.
Collision guard uses try/finally so lock is always released.
"""
import uuid
from unittest.mock import Mock

import pytest
from core.events import HypothesisCreated, ExperimentCompleted
from engines.experiment_engine import ExperimentEngine


@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_experiment_service():
    return Mock()


@pytest.fixture
def mock_health_service():
    return Mock()


@pytest.fixture
def test_engine(mock_bus, mock_experiment_service, mock_health_service):
    return ExperimentEngine(
        event_bus=mock_bus,
        experiment_service=mock_experiment_service,
        health_service=mock_health_service,
    )


def test_experiment_engine_runs_ab_test_and_emits_completed(
    test_engine, mock_bus, mock_experiment_service, mock_health_service
):
    hypothesis_id = uuid.uuid4()
    rule_id = uuid.uuid4()
    event = HypothesisCreated(
        hypothesis_id=hypothesis_id,
        rule_id=rule_id,
        reason="High confidence",
        expected_change="Increase engagement by 15%",
    )

    test_engine.handle_hypothesis_created(event)

    # Verify ExperimentService.create_experiment was called
    mock_experiment_service.create_experiment.assert_called_once()
    call_kwargs = mock_experiment_service.create_experiment.call_args[1]
    assert call_kwargs["hypothesis_id"] == hypothesis_id
    assert call_kwargs["status"] == "completed"
    assert "variant_a" in call_kwargs
    assert "variant_b" in call_kwargs
    assert "winner" in call_kwargs

    # Verify ExperimentCompleted was published
    mock_bus.publish.assert_called_once()
    published = mock_bus.publish.call_args[0][0]
    assert isinstance(published, ExperimentCompleted)
    assert published.hypothesis_id == hypothesis_id
    assert published.winner in ("variant_a", "variant_b")
    assert published.explainability != ""

    mock_health_service.heartbeat.assert_called_once_with("experiment", "healthy")


def test_experiment_engine_collision_guard_prevents_duplicate(
    test_engine, mock_bus, mock_experiment_service
):
    rule_id = uuid.uuid4()
    # Simulate an already-active experiment for this rule
    test_engine._active_target_rules.add(rule_id)

    event = HypothesisCreated(
        hypothesis_id=uuid.uuid4(),
        rule_id=rule_id,
        reason="test",
        expected_change="test",
    )
    test_engine.handle_hypothesis_created(event)

    # Should not run the experiment
    mock_experiment_service.create_experiment.assert_not_called()
    mock_bus.publish.assert_not_called()


def test_experiment_engine_releases_lock_after_completion(test_engine):
    rule_id = uuid.uuid4()
    event = HypothesisCreated(
        hypothesis_id=uuid.uuid4(),
        rule_id=rule_id,
        reason="test",
        expected_change="test",
    )
    test_engine.handle_hypothesis_created(event)
    # Lock should be released after successful completion
    assert rule_id not in test_engine._active_target_rules


def test_experiment_engine_uses_service_not_repository(test_engine):
    assert hasattr(test_engine, "experiment_service")
    assert not hasattr(test_engine, "experiments_repository")
