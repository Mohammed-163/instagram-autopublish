from __future__ import annotations

import uuid
from unittest.mock import Mock

import pytest

# Ensure container is loaded first to prevent circular import errors
import core.container

from core.events import KnowledgeCoverageCalculated
# Removed top level import to avoid circular dependency in container setup

def _get_service():
    from database.services.knowledge_coverage_service import KnowledgeCoverageService
    return KnowledgeCoverageService



@pytest.fixture
def mock_bus():
    return Mock()

@pytest.fixture
def mock_repo():
    repo = Mock()
    snapshot = Mock()
    snapshot.id = uuid.uuid4()
    repo.create.return_value = snapshot
    return repo


def test_service_creates_snapshot_and_emits_event(mock_bus, mock_repo):
    ServiceCls = _get_service()
    service = ServiceCls(
        knowledge_coverage_repository=mock_repo,
        event_bus=mock_bus
    )
    
    service.create_snapshot(
        knowledge_version="v1",
        coverage_version="v1",
        total_entities=100,
        covered_entities=10,
        unknown_entities=90,
        knowledge_coverage=0.1,
        knowledge_density=0.1,
        exploration_ratio=0.5,
        confidence_distribution={"Low": 10},
        category_distribution={"General": 10},
        feature_distribution={"feature1": 10},
        notes={"reasons": ["Test"]}
    )
    
    mock_repo.create.assert_called_once()
    mock_bus.publish.assert_called_once()
    event = mock_bus.publish.call_args[0][0]
    
    assert isinstance(event, KnowledgeCoverageCalculated)
    assert event.knowledge_coverage == 0.1


def test_service_generates_explainability():
    ServiceCls = _get_service()
    service = ServiceCls(knowledge_coverage_repository=Mock(), event_bus=Mock())
    
    class FakeSnap:
        def __init__(self, cov, den, unk):
            self.knowledge_coverage = cov
            self.knowledge_density = den
            self.unknown_entities = unk
            
    prev = FakeSnap(0.1, 0.1, 100)
    curr = FakeSnap(0.2, 0.15, 95)
    
    expl = service.generate_explainability(curr, prev)
    
    assert "Knowledge coverage increased" in expl["reasons"][0]
    assert "Knowledge density improved" in expl["reasons"][1]
