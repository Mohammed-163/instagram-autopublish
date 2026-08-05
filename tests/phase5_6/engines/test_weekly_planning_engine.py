"""
Tests for WeeklyPlanningEngine.
Engine now receives WeeklyPlanningService + KnowledgeService instead of repositories.
All planning parameters from EngineSettingsReader defaults.
"""
import uuid
from unittest.mock import Mock

import pytest
from core.events import DecisionCreated, WeeklyPlanCreated
from engines.weekly_planning_engine import WeeklyPlanningEngine


@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_weekly_planning_service():
    return Mock()


@pytest.fixture
def mock_knowledge_service():
    svc = Mock()
    svc.get_top_topic_names.return_value = ["Tech", "Design", "AI"]
    rule_mock = Mock()
    rule_mock.id = uuid.uuid4()
    svc.get_active_rules.return_value = [rule_mock]
    return svc


@pytest.fixture
def mock_health_service():
    return Mock()


@pytest.fixture
def test_engine(mock_bus, mock_weekly_planning_service, mock_knowledge_service, mock_health_service):
    return WeeklyPlanningEngine(
        event_bus=mock_bus,
        weekly_planning_service=mock_weekly_planning_service,
        knowledge_service=mock_knowledge_service,
        health_service=mock_health_service,
    )


def test_weekly_planning_engine_creates_plan_and_emits_event(
    test_engine, mock_bus, mock_weekly_planning_service, mock_knowledge_service, mock_health_service
):
    decision_id = uuid.uuid4()
    event = DecisionCreated(
        decision_id=decision_id,
        proposal_id=uuid.uuid4(),
        action="Apply variant_b style",
        status="approved",
    )

    test_engine.handle_decision_created(event)

    # Verify services were used (not repositories)
    mock_knowledge_service.get_top_topic_names.assert_called_once()
    mock_knowledge_service.get_active_rules.assert_called_once()
    mock_weekly_planning_service.create_plan.assert_called_once()

    plan_call_kwargs = mock_weekly_planning_service.create_plan.call_args[1]
    assert plan_call_kwargs["status"] == "draft"
    content_mix = plan_call_kwargs["plan_data"]
    assert "topics" in content_mix
    assert "Tech" in content_mix["topics"]
    assert str(decision_id) == content_mix["applied_decision_id"]

    # Verify WeeklyPlanCreated was published
    mock_bus.publish.assert_called_once()
    published = mock_bus.publish.call_args[0][0]
    assert isinstance(published, WeeklyPlanCreated)
    assert published.target_posts >= 7  # default planning.min_posts

    mock_health_service.heartbeat.assert_called_once_with("weekly_planning", "healthy")


def test_weekly_planning_engine_min_posts_from_settings(test_engine):
    """target_posts should be at least planning.min_posts (default 7)."""
    decision_id = uuid.uuid4()
    event = DecisionCreated(
        decision_id=decision_id,
        proposal_id=uuid.uuid4(),
        action="test",
        status="approved",
    )
    test_engine.handle_decision_created(event)
    published = test_engine.event_bus.publish.call_args[0][0]
    assert published.target_posts >= 7


def test_weekly_planning_engine_uses_services_not_repositories(test_engine):
    assert hasattr(test_engine, "weekly_planning_service")
    assert hasattr(test_engine, "knowledge_service")
    assert not hasattr(test_engine, "weekly_plans_repository")
    assert not hasattr(test_engine, "topics_repository")
    assert not hasattr(test_engine, "knowledge_rules_repository")
