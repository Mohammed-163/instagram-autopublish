"""
End-to-end integration test for Phase 2 Part 1a Pipeline (pre-publish quality):

PostPublished -> ObservationEngine -> FeatureExtractionEngine -> FeatureScoringEngine
             -> PatternDiscoveryEngine -> KnowledgeEngine -> KnowledgeUpdated

All engines are instantiated with mock SERVICES (not repositories),
verifying the Engine → Service → Repository architectural rule.

Note: FeatureScoringEngine deliberately does not depend on MetricsService —
that belongs to the separate post-publish pipeline (ObjectiveEngine ->
PerformanceEvaluationEngine, see test_performance_evaluation_engine.py and
test_objective_engine.py).
"""
import uuid
from unittest.mock import Mock

import pytest
from core.event_bus import EventBus
from core.events import PostPublished, KnowledgeUpdated, ObservationRecorded, FeaturesExtracted, FeatureScoresCalculated, PatternsDiscovered


def test_full_phase2_part1_pipeline_end_to_end():
    bus = EventBus()

    # ------------------------------------------------------------------ Mock Services
    mock_audit_service = Mock()
    mock_post_service = Mock()
    mock_feature_service = Mock()
    mock_scoring_service = Mock()
    mock_knowledge_service = Mock()
    mock_health_service = Mock()

    # Setup post mock
    post_id = uuid.uuid4()
    post_mock = Mock()
    post_mock.final_text = "Is this the future of AI?"
    mock_post_service.get_by_id.return_value = post_mock

    design_mock = Mock()
    design_mock.brightness = 0.85
    design_mock.contrast = 0.75
    mock_post_service.get_design_for_post.return_value = design_mock

    # FeatureService returns feature map for pattern discovery
    mock_feature_service.get_feature_map.return_value = {
        "has_question": 1.0,
        "text_length": 150.0,
    }
    # ScoringService returns score map for pattern discovery
    mock_scoring_service.get_score_map.return_value = {}

    # KnowledgeService version mock
    version_mock = Mock()
    version_id = uuid.uuid4()
    version_mock.id = version_id
    mock_knowledge_service.create_knowledge_version.return_value = version_mock

    # ------------------------------------------------------------------ Instantiate Engines with Services
    from engines.observation_engine import ObservationEngine
    from engines.feature_extraction_engine import FeatureExtractionEngine
    from engines.feature_scoring_engine import FeatureScoringEngine
    from engines.pattern_discovery_engine import PatternDiscoveryEngine
    from engines.knowledge_engine import KnowledgeEngine

    obs_engine = ObservationEngine(event_bus=bus, audit_service=mock_audit_service, health_service=mock_health_service)
    feat_engine = FeatureExtractionEngine(event_bus=bus, post_service=mock_post_service, feature_service=mock_feature_service, health_service=mock_health_service)
    score_engine = FeatureScoringEngine(event_bus=bus, scoring_service=mock_scoring_service, health_service=mock_health_service)
    pattern_engine = PatternDiscoveryEngine(event_bus=bus, feature_service=mock_feature_service, scoring_service=mock_scoring_service, health_service=mock_health_service)
    know_engine = KnowledgeEngine(event_bus=bus, knowledge_service=mock_knowledge_service, health_service=mock_health_service)

    # ------------------------------------------------------------------ Wire
    bus.subscribe(PostPublished, obs_engine.handle_post_published)
    bus.subscribe(ObservationRecorded, feat_engine.handle_observation_recorded)
    bus.subscribe(FeaturesExtracted, score_engine.handle_features_extracted)
    bus.subscribe(FeatureScoresCalculated, pattern_engine.handle_feature_scores_calculated)
    bus.subscribe(PatternsDiscovered, know_engine.handle_patterns_discovered)

    received_knowledge_events = []
    bus.subscribe(KnowledgeUpdated, lambda e: received_knowledge_events.append(e))

    # ------------------------------------------------------------------ Trigger
    bus.publish(PostPublished(post_id=post_id))

    # ------------------------------------------------------------------ Verify: pipeline completed end-to-end
    assert len(received_knowledge_events) >= 1
    assert received_knowledge_events[0].knowledge_version_id == version_id

    # Each engine used Services, not repositories
    mock_audit_service.record_event.assert_called_once()
    mock_post_service.get_by_id.assert_called_once_with(post_id)
    mock_feature_service.upsert_features.assert_called_once()
    mock_scoring_service.upsert_scores.assert_called_once()
    mock_knowledge_service.create_rule.assert_called()
    mock_knowledge_service.create_knowledge_version.assert_called()

    # Heartbeats reported
    mock_health_service.heartbeat.assert_any_call("observation", "healthy")
    mock_health_service.heartbeat.assert_any_call("feature_extraction", "healthy")
    mock_health_service.heartbeat.assert_any_call("feature_scoring", "healthy")
    mock_health_service.heartbeat.assert_any_call("pattern_discovery", "healthy")
    mock_health_service.heartbeat.assert_any_call("knowledge", "healthy")
