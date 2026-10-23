"""
Tests for HypothesisEngine.
Engine now receives HypothesisService instead of hypotheses_repository.
Threshold (0.4) from EngineSettingsReader default.
"""
import uuid
from unittest.mock import Mock

import pytest
from core.events import ConfidenceUpdated, HypothesisCreated
from engines.hypothesis_engine import HypothesisEngine


@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_hypothesis_service():
    return Mock()


@pytest.fixture
def mock_health_service():
    return Mock()


@pytest.fixture
def test_engine(mock_bus, mock_hypothesis_service, mock_health_service):
    return HypothesisEngine(
        event_bus=mock_bus,
        hypothesis_service=mock_hypothesis_service,
        health_service=mock_health_service,
    )


def test_hypothesis_engine_generates_hypothesis_for_valid_confidence(
    test_engine, mock_bus, mock_hypothesis_service, mock_health_service
):
    rule_id = uuid.uuid4()
    event = ConfidenceUpdated(
        rule_id=rule_id,
        confidence_score=0.85,
        sample_size=12,
        success_count=10,
        failure_count=2,
        reasoning="High ratio observed",
    )

    test_engine.handle_confidence_updated(event)

    # Verify HypothesisService.create was called (not repository)
    mock_hypothesis_service.create.assert_called_once()
    call_kwargs = mock_hypothesis_service.create.call_args[1]
    assert call_kwargs["rule_id"] == rule_id
    assert call_kwargs["status"] == "proposed"

    # Verify HypothesisCreated was published with explainability
    mock_bus.publish.assert_called_once()
    published = mock_bus.publish.call_args[0][0]
    assert isinstance(published, HypothesisCreated)
    assert published.rule_id == rule_id
    assert published.explainability != ""
    assert "15" in published.expected_change  # default increase pct

    mock_health_service.heartbeat.assert_called_once_with("hypothesis", "healthy")


def test_hypothesis_engine_skips_low_confidence(test_engine, mock_bus, mock_hypothesis_service):
    rule_id = uuid.uuid4()
    event = ConfidenceUpdated(
        rule_id=rule_id,
        confidence_score=0.2,  # below default threshold 0.4
        sample_size=2,
        reasoning="Low sample size",
    )

    test_engine.handle_confidence_updated(event)

    mock_hypothesis_service.create.assert_not_called()
    mock_bus.publish.assert_not_called()


def test_hypothesis_engine_uses_service_not_repository(test_engine):
    assert hasattr(test_engine, "hypothesis_service")
    assert not hasattr(test_engine, "hypotheses_repository")
