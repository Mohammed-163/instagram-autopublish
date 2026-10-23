"""
Tests for ConfidenceEngine.
Engine now receives KnowledgeService + ConfidenceService instead of repositories.
_get_setting() helper removed — thresholds from EngineSettingsReader with defaults.
"""
import uuid
from unittest.mock import Mock

import pytest
from core.events import KnowledgeUpdated, ConfidenceUpdated
from engines.confidence_engine import ConfidenceEngine


@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_knowledge_service():
    svc = Mock()
    rule_mock = Mock()
    rule_mock.id = uuid.uuid4()
    rule_mock.name = "Test Question Rule"
    rule_mock.success_count = 10
    rule_mock.failure_count = 2
    svc.get_active_rules.return_value = [rule_mock]
    return svc


@pytest.fixture
def mock_confidence_service():
    return Mock()


@pytest.fixture
def mock_health_service():
    return Mock()


@pytest.fixture
def test_engine(mock_bus, mock_knowledge_service, mock_confidence_service, mock_health_service):
    return ConfidenceEngine(
        event_bus=mock_bus,
        knowledge_service=mock_knowledge_service,
        confidence_service=mock_confidence_service,
        health_service=mock_health_service,
    )


def test_confidence_engine_evaluates_rules_and_emits_event(
    test_engine, mock_bus, mock_knowledge_service, mock_confidence_service, mock_health_service
):
    event = KnowledgeUpdated(knowledge_version_id=uuid.uuid4(), summary="Updated")
    test_engine.handle_knowledge_updated(event)

    # Verify KnowledgeService was used
    mock_knowledge_service.get_active_rules.assert_called_once()

    # Verify ConfidenceService.record_score was called
    mock_confidence_service.record_score.assert_called_once()
    call_kwargs = mock_confidence_service.record_score.call_args[1]
    assert "rule_id" in call_kwargs
    assert "confidence_score" in call_kwargs
    assert call_kwargs["confidence_score"] > 0

    # Verify ConfidenceUpdated was published
    mock_bus.publish.assert_called_once()
    published = mock_bus.publish.call_args[0][0]
    assert isinstance(published, ConfidenceUpdated)
    assert published.confidence_score > 0.5
    assert published.reasoning != ""

    mock_health_service.heartbeat.assert_called_once_with("confidence", "healthy")


def test_confidence_engine_uses_services_not_repositories(test_engine):
    assert hasattr(test_engine, "knowledge_service")
    assert hasattr(test_engine, "confidence_service")
    assert not hasattr(test_engine, "knowledge_rules_repository")
    assert not hasattr(test_engine, "confidence_scores_repository")
    assert not hasattr(test_engine, "settings_repository")


def test_confidence_engine_calculation_respects_sample_size(test_engine):
    """Below min_sample_size (5), returns base_confidence (0.5)."""
    rule_mock = Mock()
    rule_mock.name = "Small Sample Rule"
    rule_mock.success_count = 2
    rule_mock.failure_count = 1
    score, reasoning = test_engine._calculate_confidence(
        rule=rule_mock,
        sample_size=3,
        success_count=2,
        failure_count=1,
        min_sample_size=5.0,
        base_confidence=0.5,
        success_weight=0.1,
    )
    assert score == pytest.approx(0.5)
    assert "ratio" in reasoning
