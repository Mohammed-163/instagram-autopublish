from __future__ import annotations

import uuid
from unittest.mock import Mock, call

import pytest

# Ensure container is loaded first to prevent circular import errors
import core.container

from core.events import KnowledgeUpdated, KnowledgeCoverageCalculated
from engines.knowledge_coverage_engine import KnowledgeCoverageEngine


@pytest.fixture
def mock_bus():
    return Mock()

@pytest.fixture
def mock_knowledge_service():
    service = Mock()
    # Mocking active rules for deterministic test
    rule1 = Mock()
    rule1.confidence = 0.2
    rule2 = Mock()
    rule2.confidence = 0.5
    rule3 = Mock()
    rule3.confidence = 0.7
    rule4 = Mock()
    rule4.confidence = 0.9
    service.get_active_rules.return_value = [rule1, rule2, rule3, rule4]
    service.get_knowledge_statistics.return_value = {}
    return service

@pytest.fixture
def mock_knowledge_coverage_service():
    service = Mock()
    service.get_latest_snapshot.return_value = None
    service.generate_explainability.return_value = {"reasons": ["Test explainability"]}
    return service

@pytest.fixture
def mock_settings_service():
    service = Mock()
    service.get.return_value = {
        "stable_rule_threshold": 0.8,
        "min_sample_size": 30
    }
    return service

@pytest.fixture
def engine(mock_bus, mock_knowledge_service, mock_knowledge_coverage_service, mock_settings_service):
    return KnowledgeCoverageEngine(
        event_bus=mock_bus,
        knowledge_service=mock_knowledge_service,
        knowledge_coverage_service=mock_knowledge_coverage_service,
        feature_service=Mock(),
        settings_service=mock_settings_service,
        health_service=Mock(),
    )


def test_knowledge_coverage_engine_calculates_metrics_and_saves_snapshot(
    engine, mock_knowledge_coverage_service, mock_settings_service
):
    event = KnowledgeUpdated(knowledge_version_id=uuid.uuid4(), summary="Test update")
    engine.handle_knowledge_updated(event)
    
    # We do not assert get_settings here directly since it goes through reader
    
    mock_knowledge_coverage_service.create_snapshot.assert_called_once()
    kwargs = mock_knowledge_coverage_service.create_snapshot.call_args[1]
    
    assert kwargs["total_entities"] == 100
    assert kwargs["covered_entities"] == 4
    assert kwargs["unknown_entities"] == 96
    assert kwargs["knowledge_coverage"] == 0.04
    assert kwargs["knowledge_density"] == 0.04
    
    dist = kwargs["confidence_distribution"]
    assert dist["Low"] == 1
    assert dist["Medium"] == 1
    assert dist["High"] == 1
    assert dist["Very High"] == 1
    
    assert kwargs["notes"] == {"reasons": ["Test explainability"]}

def test_engine_is_deterministic(engine, mock_knowledge_coverage_service):
    event = KnowledgeUpdated(knowledge_version_id=uuid.uuid4(), summary="Test")
    engine.handle_knowledge_updated(event)
    kwargs1 = mock_knowledge_coverage_service.create_snapshot.call_args[1]
    
    engine.handle_knowledge_updated(event)
    kwargs2 = mock_knowledge_coverage_service.create_snapshot.call_args[1]
    
    assert kwargs1 == kwargs2

def test_engine_handles_errors_gracefully(engine, mock_knowledge_service):
    mock_knowledge_service.get_active_rules.side_effect = Exception("DB error")
    
    event = KnowledgeUpdated(knowledge_version_id=uuid.uuid4(), summary="Test")
    engine.handle_knowledge_updated(event)
    
    engine._health_service.heartbeat.assert_called_with("knowledge_coverage", "error", error="DB error")
