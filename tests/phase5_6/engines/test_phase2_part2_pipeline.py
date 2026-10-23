"""
End-to-end integration test for Phase 2 Part 2 Closed Learning Loop:

KnowledgeUpdated -> ConfidenceEngine -> HypothesisEngine -> ExperimentEngine
                -> DecisionEngine -> WeeklyPlanningEngine -> WeeklyPlanCreated

All engines instantiated with mock SERVICES (not repositories).
"""
import uuid
from unittest.mock import Mock

import pytest
from core.event_bus import EventBus
from core.events import (
    KnowledgeUpdated,
    ConfidenceUpdated,
    HypothesisCreated,
    ExperimentCompleted,
    DecisionProposed,
    DecisionCreated,
    WeeklyPlanCreated,
)


def test_full_phase2_part2_closed_learning_loop_pipeline():
    bus = EventBus()

    # ------------------------------------------------------------------ Mock Services
    mock_knowledge_service = Mock()
    mock_confidence_service = Mock()
    mock_hypothesis_service = Mock()
    mock_experiment_service = Mock()
    mock_decision_service = Mock()
    mock_weekly_planning_service = Mock()
    mock_health_service = Mock()

    # Setup rule data via KnowledgeService
    rule_id = uuid.uuid4()
    rule_mock = Mock()
    rule_mock.id = rule_id
    rule_mock.name = "Question Header Rule"
    rule_mock.success_count = 15
    rule_mock.failure_count = 3
    mock_knowledge_service.get_active_rules.return_value = [rule_mock]
    mock_knowledge_service.get_top_topic_names.return_value = ["Tech Insights", "Design"]

    version_mock = Mock()
    version_mock.id = uuid.uuid4()
    mock_knowledge_service.create_knowledge_version.return_value = version_mock

    # ------------------------------------------------------------------ Instantiate Part 2 Engines
    from engines.confidence_engine import ConfidenceEngine
    from engines.hypothesis_engine import HypothesisEngine
    from engines.experiment_engine import ExperimentEngine
    from engines.decision_engine import DecisionEngine
    from engines.weekly_planning_engine import WeeklyPlanningEngine

    conf_engine = ConfidenceEngine(event_bus=bus, knowledge_service=mock_knowledge_service, confidence_service=mock_confidence_service, health_service=mock_health_service)
    hypo_engine = HypothesisEngine(event_bus=bus, hypothesis_service=mock_hypothesis_service, health_service=mock_health_service)
    exp_engine = ExperimentEngine(event_bus=bus, experiment_service=mock_experiment_service, health_service=mock_health_service)
    dec_engine = DecisionEngine(event_bus=bus, decision_service=mock_decision_service, health_service=mock_health_service)
    plan_engine = WeeklyPlanningEngine(event_bus=bus, weekly_planning_service=mock_weekly_planning_service, knowledge_service=mock_knowledge_service, health_service=mock_health_service)

    # ------------------------------------------------------------------ Wire
    bus.subscribe(KnowledgeUpdated, conf_engine.handle_knowledge_updated)
    bus.subscribe(ConfidenceUpdated, hypo_engine.handle_confidence_updated)
    bus.subscribe(HypothesisCreated, exp_engine.handle_hypothesis_created)
    bus.subscribe(ExperimentCompleted, dec_engine.handle_experiment_completed)
    bus.subscribe(DecisionCreated, plan_engine.handle_decision_created)

    received_plan_events = []
    bus.subscribe(WeeklyPlanCreated, lambda e: received_plan_events.append(e))

    # ------------------------------------------------------------------ Trigger
    version_id = uuid.uuid4()
    bus.publish(KnowledgeUpdated(knowledge_version_id=version_id, summary="New pattern discovered"))

    # ------------------------------------------------------------------ Verify: full loop completed
    assert len(received_plan_events) == 1
    published_plan = received_plan_events[0]
    assert isinstance(published_plan, WeeklyPlanCreated)
    assert published_plan.target_posts >= 7

    # Verify each engine used Services
    mock_knowledge_service.get_active_rules.assert_called()
    mock_confidence_service.record_score.assert_called()
    mock_hypothesis_service.create.assert_called()
    mock_experiment_service.create_experiment.assert_called()
    mock_decision_service.log_engine_decision.assert_called()
    mock_weekly_planning_service.create_plan.assert_called()

    # Verify heartbeats
    mock_health_service.heartbeat.assert_any_call("confidence", "healthy")
    mock_health_service.heartbeat.assert_any_call("hypothesis", "healthy")
    mock_health_service.heartbeat.assert_any_call("experiment", "healthy")
    mock_health_service.heartbeat.assert_any_call("decision", "healthy")
    mock_health_service.heartbeat.assert_any_call("weekly_planning", "healthy")
