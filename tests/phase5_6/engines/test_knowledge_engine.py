"""
Tests for KnowledgeEngine.
Engine now receives KnowledgeService instead of repositories.
"""
import uuid
from unittest.mock import Mock

import pytest
from core.events import PatternsDiscovered, KnowledgeUpdated
from engines.knowledge_engine import KnowledgeEngine


@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_knowledge_service():
    svc = Mock()
    version_mock = Mock()
    version_mock.id = uuid.uuid4()
    svc.create_knowledge_version.return_value = version_mock
    return svc


@pytest.fixture
def mock_health_service():
    return Mock()


@pytest.fixture
def test_engine(mock_bus, mock_knowledge_service, mock_health_service):
    return KnowledgeEngine(
        event_bus=mock_bus,
        knowledge_service=mock_knowledge_service,
        health_service=mock_health_service,
    )


def test_knowledge_engine_creates_rule_and_emits_updated(
    test_engine, mock_bus, mock_knowledge_service, mock_health_service
):
    pattern_id = uuid.uuid4()
    event = PatternsDiscovered(
        pattern_id=pattern_id,
        pattern_name="Test Pattern",
        conditions={"feature_key": "has_question", "operator": "==", "target_value": 1.0},
        confidence_score=0.75,
        metrics_summary={"overall_score": 0.85},
    )

    test_engine.handle_patterns_discovered(event)

    # Verify KnowledgeService was used (not repositories)
    mock_knowledge_service.create_rule.assert_called_once()
    rule_call = mock_knowledge_service.create_rule.call_args[1]
    assert rule_call["name"] == "Test Pattern"

    mock_knowledge_service.create_knowledge_version.assert_called_once()

    # Verify KnowledgeUpdated was published
    mock_bus.publish.assert_called_once()
    published = mock_bus.publish.call_args[0][0]
    assert isinstance(published, KnowledgeUpdated)
    assert "Test Pattern" in published.summary

    mock_health_service.heartbeat.assert_called_once_with("knowledge", "healthy")


def test_knowledge_engine_uses_service_not_repositories(test_engine):
    assert hasattr(test_engine, "knowledge_service")
    assert not hasattr(test_engine, "knowledge_rules_repository")
    assert not hasattr(test_engine, "knowledge_versions_repository")
