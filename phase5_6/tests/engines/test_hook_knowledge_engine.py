"""
Tests for HookKnowledgeEngine (Phase 4 Part 1, item 4).
"""
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.events import HookAnalyzed, HookRuleCreated
from engines.hook_knowledge_engine import HookKnowledgeEngine


@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_hook_service():
    return Mock()


@pytest.fixture
def mock_scoring_service():
    svc = Mock()
    svc.get_score_map.return_value = {"overall_score": 0.9}
    return svc


@pytest.fixture
def mock_health_service():
    return Mock()


@pytest.fixture
def test_engine(mock_bus, mock_hook_service, mock_scoring_service, mock_health_service):
    return HookKnowledgeEngine(
        event_bus=mock_bus,
        hook_service=mock_hook_service,
        scoring_service=mock_scoring_service,
        health_service=mock_health_service,
    )


def _statistic(is_rule, **overrides):
    defaults = dict(
        id=uuid.uuid4(), success_level="high", confidence=0.8, sample_size=6,
    )
    defaults.update(overrides)
    return SimpleNamespace(is_rule=is_rule, **defaults)


def test_handle_hook_analyzed_updates_statistic(
    test_engine, mock_hook_service, mock_scoring_service
):
    post_id = uuid.uuid4()
    mock_hook_service.record_observation.return_value = _statistic(is_rule=False)

    event = HookAnalyzed(post_id=post_id, hook_text="hook", hook_type="curiosity", category="Science", features={})
    test_engine.handle_hook_analyzed(event)

    mock_scoring_service.get_score_map.assert_called_once_with(post_id)
    mock_hook_service.record_observation.assert_called_once()
    kwargs = mock_hook_service.record_observation.call_args[1]
    assert kwargs["category"] == "Science"
    assert kwargs["hook_type"] == "curiosity"
    assert kwargs["success_score"] == 0.9


def test_handle_hook_analyzed_emits_rule_when_statistic_qualifies(
    test_engine, mock_bus, mock_hook_service
):
    statistic_id = uuid.uuid4()
    mock_hook_service.record_observation.return_value = _statistic(is_rule=True, id=statistic_id)

    event = HookAnalyzed(
        post_id=uuid.uuid4(), hook_text="hook", hook_type="curiosity", category="Science", features={}
    )
    test_engine.handle_hook_analyzed(event)

    mock_bus.publish.assert_called_once()
    published = mock_bus.publish.call_args[0][0]
    assert isinstance(published, HookRuleCreated)
    assert published.statistic_id == statistic_id
    assert published.category == "Science"
    assert published.hook_type == "curiosity"
    assert published.success_level == "high"


def test_handle_hook_analyzed_no_event_when_statistic_not_yet_a_rule(
    test_engine, mock_bus, mock_hook_service
):
    mock_hook_service.record_observation.return_value = _statistic(is_rule=False)

    event = HookAnalyzed(
        post_id=uuid.uuid4(), hook_text="hook", hook_type="question", category="Psychology", features={}
    )
    test_engine.handle_hook_analyzed(event)

    mock_bus.publish.assert_not_called()


def test_handle_hook_analyzed_defaults_category_when_missing(
    test_engine, mock_hook_service
):
    mock_hook_service.record_observation.return_value = _statistic(is_rule=False)
    event = HookAnalyzed(post_id=uuid.uuid4(), hook_text="hook", hook_type="curiosity", category=None, features={})
    test_engine.handle_hook_analyzed(event)

    kwargs = mock_hook_service.record_observation.call_args[1]
    assert kwargs["category"] == "General"


def test_handle_hook_analyzed_reports_heartbeat(test_engine, mock_health_service, mock_hook_service):
    mock_hook_service.record_observation.return_value = _statistic(is_rule=False)
    test_engine.handle_hook_analyzed(
        HookAnalyzed(post_id=uuid.uuid4(), hook_text="h", hook_type="curiosity", category="Science", features={})
    )
    mock_health_service.heartbeat.assert_called_once_with("hook_knowledge", "healthy")
