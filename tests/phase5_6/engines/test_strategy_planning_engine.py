"""
Tests for StrategyPlanningEngine (Phase 4 Part 1, items 1, 2, 6, 7, 10).
Planning-only: verifies the engine never executes a publish decision, only
persists StrategyCandidate rows and emits StrategyGenerated / WeeklyStrategyCompleted.
"""
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.events import StrategyGenerated, WeeklyStrategyCompleted
from engines.strategy_planning_engine import StrategyPlanningEngine


@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_strategy_service():
    svc = Mock()
    version = SimpleNamespace(id=uuid.uuid4(), version_number=1)
    svc.create_version.return_value = version
    svc.get_recent_candidates.return_value = []

    svc.add_candidate.side_effect = lambda **kwargs: SimpleNamespace(id=uuid.uuid4())
    return svc


@pytest.fixture
def mock_opportunity_service():
    service = Mock()
    service.get_by_status.return_value = [SimpleNamespace(
        id=uuid.uuid4(),
        evidence={"categories": ["Hope", "Patience"], "raw_data": {"hook_type": "evidence_hook"}},
        related_entities=[f"Topic {index}" for index in range(10)],
        opportunity_score=0.85,
        confidence=0.9,
        expected_gain=0.8,
    )]
    return service


@pytest.fixture
def mock_health_service():
    return Mock()


@pytest.fixture
def test_engine(mock_bus, mock_strategy_service, mock_opportunity_service, mock_health_service):
    return StrategyPlanningEngine(
        event_bus=mock_bus,
        strategy_service=mock_strategy_service,
        opportunity_service=mock_opportunity_service,
        health_service=mock_health_service,
    )


def test_generate_weekly_strategy_creates_version_and_candidates(
    test_engine, mock_strategy_service, mock_bus
):
    version_id = test_engine.generate_weekly_strategy(
        week_start=date(2026, 8, 3), week_end=date(2026, 8, 9), target_posts=7
    )

    mock_strategy_service.create_version.assert_called_once()
    assert mock_strategy_service.add_candidate.call_count == 7
    assert version_id is not None


def test_generate_weekly_strategy_never_calls_publish_or_schedule_apis(
    test_engine, mock_strategy_service
):
    """This is planning-only: the engine must not touch anything that looks
    like a publish/schedule action."""
    test_engine.generate_weekly_strategy(target_posts=7)
    forbidden = {"publish_post", "schedule_post", "execute_decision"}
    used_attrs = {c[0] for c in mock_strategy_service.method_calls}
    assert forbidden.isdisjoint(used_attrs)


def test_candidates_have_no_two_consecutive_same_category(test_engine, mock_strategy_service):
    test_engine.generate_weekly_strategy(target_posts=7)
    categories = [c.kwargs["category"] for c in mock_strategy_service.add_candidate.call_args_list]
    for a, b in zip(categories, categories[1:]):
        assert a != b


def test_candidates_have_no_two_consecutive_same_hook_type(test_engine, mock_strategy_service):
    test_engine.generate_weekly_strategy(target_posts=7)
    hook_types = [c.kwargs["hook_type"] for c in mock_strategy_service.add_candidate.call_args_list]
    for a, b in zip(hook_types, hook_types[1:]):
        assert a != b


def test_candidates_have_no_repeated_topics_within_week(test_engine, mock_strategy_service):
    test_engine.generate_weekly_strategy(target_posts=7)
    topics = [c.kwargs["topic"] for c in mock_strategy_service.add_candidate.call_args_list]
    assert len(topics) == len(set(topics))


def test_each_candidate_is_fully_explainable(test_engine, mock_strategy_service):
    test_engine.generate_weekly_strategy(target_posts=7)
    for call in mock_strategy_service.add_candidate.call_args_list:
        kwargs = call.kwargs
        assert kwargs["reason"]
        assert kwargs["confidence"] is not None
        assert kwargs["expected_success"] is not None
        assert kwargs["is_experiment"] in (True, False)
        assert kwargs["based_on"]


def test_exploitation_uses_validated_opportunity(
    test_engine, mock_strategy_service, mock_opportunity_service
):
    test_engine.generate_weekly_strategy(target_posts=7)

    calls = mock_strategy_service.add_candidate.call_args_list
    exploitation_reason_calls = [c for c in calls if "Exploitation" in c.kwargs["reason"]]
    assert exploitation_reason_calls, "expected at least one slot to use the validated opportunity"
    mock_opportunity_service.get_by_status.assert_called_once_with("Validated")
    for c in exploitation_reason_calls:
        assert c.kwargs["is_experiment"] is False


def test_weekly_strategy_completed_event_emitted_after_all_candidates(
    test_engine, mock_bus
):
    test_engine.generate_weekly_strategy(target_posts=7)
    published_types = [type(c[0][0]) for c in mock_bus.publish.call_args_list]
    assert StrategyGenerated in published_types
    assert published_types[-1] is WeeklyStrategyCompleted
    assert published_types.count(StrategyGenerated) == 7


def test_target_posts_respects_settings_minimum(test_engine, mock_strategy_service):
    test_engine.generate_weekly_strategy(target_posts=1)
    # default strategy.min_posts is 7 -> engine should raise the floor
    assert mock_strategy_service.add_candidate.call_count >= 7


def test_records_explanation_for_the_whole_version(test_engine, mock_strategy_service):
    test_engine.generate_weekly_strategy(target_posts=7)
    mock_strategy_service.record_explanation.assert_called_once()
    kwargs = mock_strategy_service.record_explanation.call_args[1]
    assert "explanation" in kwargs
    assert "factors" in kwargs


def test_heartbeat_reported_healthy(test_engine, mock_health_service):
    test_engine.generate_weekly_strategy(target_posts=7)
    mock_health_service.heartbeat.assert_called_once_with("strategy_planning", "healthy")
