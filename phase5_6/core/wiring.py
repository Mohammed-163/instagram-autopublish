"""
Wires the default subscribers onto the process-wide event bus.

Full Closed Learning Loop Pipeline:

  Part 1a (Pre-publish quality pipeline):
  PostPublished -> ObservationEngine (ObservationRecorded)
               -> FeatureExtractionEngine (FeaturesExtracted)
               -> FeatureScoringEngine (FeatureScoresCalculated)
               -> PatternDiscoveryEngine (PatternsDiscovered)
               -> KnowledgeEngine (KnowledgeUpdated)

  Part 1b (Post-publish performance pipeline — runs later, once real metrics
  exist for the post; independent of Part 1a's timing):
  MetricNormalized -> ObjectiveEngine (SuccessScoreCalculated)
                   -> PerformanceEvaluationEngine (PerformanceEvaluated)

  FeatureScoringEngine and PerformanceEvaluationEngine are deliberately two
  separate engines rather than one: the former only ever sees a post before
  it is published (content quality alone), the latter only ever sees a post
  after real performance data exists (quality vs. actual outcome). Wiring
  the same engine to both events was the Part 1a/1b mismatch that used to
  live in a single ScoringEngine — split here on purpose.

  Part 2 (Closed Learning Loop Pipeline):
  KnowledgeUpdated -> ConfidenceEngine (ConfidenceUpdated)
                   -> HypothesisEngine (HypothesisCreated)
                   -> ExperimentEngine (ExperimentCompleted)
                   -> DecisionEngine (DecisionProposed -> Policy Check -> DecisionCreated)
                   -> WeeklyPlanningEngine (WeeklyPlanCreated)

Architectural rules enforced here:
- Every engine receives ONLY Service-layer objects in its constructor.
- No engine receives a repository, a DB session, or any SQL object.
- This is the ONLY place that knows the full pipeline shape.
"""
from __future__ import annotations

from core.event_bus import EventBus, event_bus as default_event_bus
from core.events import (
    PostPublished,
    ObservationRecorded,
    FeaturesExtracted,
    FeatureScoresCalculated,
    PatternsDiscovered,
    KnowledgeUpdated,
    ConfidenceUpdated,
    HypothesisCreated,
    ExperimentCompleted,
    DecisionCreated,
    RuleActivated,
    HookAnalyzed,
    MetricNormalized,
    SuccessScoreCalculated,
    KnowledgeCoverageCalculated,
    WeeklyStrategyCompleted,
    DecisionCandidateApproved,
)


def wire_default_subscribers(bus: EventBus = default_event_bus) -> None:
    # ------------------------------------------------------------------ Services
    from database.services.audit_service import audit_service
    from database.services.confidence_service import confidence_service
    from database.services.decision_service import decision_service
    from database.services.experiment_service import experiment_service
    from database.services.feature_service import feature_service
    from database.services.hook_service import hook_service
    from database.services.hook_structure_service import hook_structure_service
    from database.services.hypothesis_service import hypothesis_service
    from database.services.knowledge_service import knowledge_service
    from database.services.knowledge_coverage_service import knowledge_coverage_service
    from database.services.metrics_service import metrics_service
    from database.services.notification_service import notification_service
    from database.services.opportunity_service import opportunity_service
    from database.services.post_service import post_service
    from database.services.scoring_service import scoring_service
    from database.services.settings_service import settings_service
    from database.services.strategy_service import strategy_service
    from database.services.weekly_planning_service import weekly_planning_service
    from database.services.phase5_decision_service import phase5_decision_service

    # ------------------------------------------------------------------ Part 1a Engines (pre-publish quality)
    from engines.observation_engine import ObservationEngine
    from engines.feature_extraction_engine import FeatureExtractionEngine
    from engines.feature_scoring_engine import FeatureScoringEngine
    from engines.pattern_discovery_engine import PatternDiscoveryEngine
    from engines.knowledge_engine import KnowledgeEngine

    # ------------------------------------------------------------------ Part 1b Engines (post-publish performance)
    from engines.objective_engine import ObjectiveEngine
    from engines.performance_evaluation_engine import PerformanceEvaluationEngine

    # ------------------------------------------------------------------ Part 2 Engines
    from engines.confidence_engine import ConfidenceEngine
    from engines.hypothesis_engine import HypothesisEngine
    from engines.experiment_engine import ExperimentEngine
    from engines.decision_engine import DecisionEngine
    from engines.weekly_planning_engine import WeeklyPlanningEngine
    from engines.knowledge_coverage_engine import KnowledgeCoverageEngine

    # ------------------------------------------------------------------ Phase 4 Part 1 Engines
    from engines.hook_pattern_engine import HookPatternDiscoveryEngine
    from engines.hook_knowledge_engine import HookKnowledgeEngine
    from engines.strategy_planning_engine import StrategyPlanningEngine

    # ------------------------------------------------------------------ Phase 4 Part 2 Engines
    from engines.hook_structure_learning_engine import HookStructureLearningEngine
    from engines.opportunity_discovery_engine import OpportunityDiscoveryEngine

    # ------------------------------------------------------------------ Phase 5 Part 1 Engine
    from engines.phase5_decision_engine import Phase5DecisionEngine

    # ------------------------------------------------------------------ Phase 6 Part 1 Engine
    from engines.phase6_execution_engine import Phase6ExecutionEngine

    # ------------------------------------------------------------------ Instantiate Part 1a
    observation_engine = ObservationEngine(
        event_bus=bus,
        audit_service=audit_service,
        settings_service=settings_service,
    )
    feature_extraction_engine = FeatureExtractionEngine(
        event_bus=bus,
        post_service=post_service,
        feature_service=feature_service,
        settings_service=settings_service,
    )
    feature_scoring_engine = FeatureScoringEngine(
        event_bus=bus,
        scoring_service=scoring_service,
        settings_service=settings_service,
    )
    pattern_discovery_engine = PatternDiscoveryEngine(
        event_bus=bus,
        feature_service=feature_service,
        scoring_service=scoring_service,
        settings_service=settings_service,
    )
    knowledge_engine = KnowledgeEngine(
        event_bus=bus,
        knowledge_service=knowledge_service,
        settings_service=settings_service,
    )

    # ------------------------------------------------------------------ Instantiate Part 1b
    objective_engine = ObjectiveEngine(
        event_bus=bus,
        metrics_service=metrics_service,
        settings_service=settings_service,
    )
    performance_evaluation_engine = PerformanceEvaluationEngine(
        event_bus=bus,
        scoring_service=scoring_service,
        settings_service=settings_service,
    )

    # ------------------------------------------------------------------ Instantiate Part 2
    confidence_engine = ConfidenceEngine(
        event_bus=bus,
        knowledge_service=knowledge_service,
        confidence_service=confidence_service,
        settings_service=settings_service,
    )
    hypothesis_engine = HypothesisEngine(
        event_bus=bus,
        hypothesis_service=hypothesis_service,
        settings_service=settings_service,
    )
    experiment_engine = ExperimentEngine(
        event_bus=bus,
        experiment_service=experiment_service,
        settings_service=settings_service,
    )
    decision_engine = DecisionEngine(
        event_bus=bus,
        decision_service=decision_service,
        settings_service=settings_service,
    )
    weekly_planning_engine = WeeklyPlanningEngine(
        event_bus=bus,
        weekly_planning_service=weekly_planning_service,
        knowledge_service=knowledge_service,
        settings_service=settings_service,
    )

    # ------------------------------------------------------------------ Instantiate Phase 4 Part 1
    hook_pattern_discovery_engine = HookPatternDiscoveryEngine(
        event_bus=bus,
        post_service=post_service,
        hook_service=hook_service,
        settings_service=settings_service,
    )
    hook_knowledge_engine = HookKnowledgeEngine(
        event_bus=bus,
        hook_service=hook_service,
        scoring_service=scoring_service,
        settings_service=settings_service,
    )
    strategy_planning_engine = StrategyPlanningEngine(
        event_bus=bus,
        strategy_service=strategy_service,
        opportunity_service=opportunity_service,
        settings_service=settings_service,
    )

    # ------------------------------------------------------------------ Instantiate Phase 4 Part 2
    hook_structure_learning_engine = HookStructureLearningEngine(
        event_bus=bus,
        hook_structure_service=hook_structure_service,
        settings_service=settings_service,
    )
    knowledge_coverage_engine = KnowledgeCoverageEngine(
        event_bus=bus,
        knowledge_coverage_service=knowledge_coverage_service,
        knowledge_service=knowledge_service,
        feature_service=feature_service,
        settings_service=settings_service,
    )
    opportunity_discovery_engine = OpportunityDiscoveryEngine(
        event_bus=bus,
        opportunity_service=opportunity_service,
        knowledge_service=knowledge_service,
        knowledge_coverage_service=knowledge_coverage_service,
        feature_service=feature_service,
        settings_service=settings_service,
    )

    # ------------------------------------------------------------------ Instantiate Phase 6 Part 1 & Part 3
    from database.services.phase6_execution_service import phase6_execution_service
    from engines.execution.orchestrator import execution_orchestrator
    from engines.execution.factory import execution_plan_factory

    phase6_execution_engine = Phase6ExecutionEngine(
        event_bus=bus,
        phase6_execution_service=phase6_execution_service,
        execution_orchestrator=execution_orchestrator,
        execution_plan_factory=execution_plan_factory,
        settings_service=settings_service,
    )

    # ------------------------------------------------------------------ Instantiate Phase 5 Part 1
    phase5_decision_engine = Phase5DecisionEngine(
        event_bus=bus,
        phase5_decision_service=phase5_decision_service,
        strategy_service=strategy_service,
        settings_service=settings_service,
    )

    # ------------------------------------------------------------------ Wire Part 1a
    bus.subscribe(PostPublished, observation_engine.handle_post_published)
    bus.subscribe(ObservationRecorded, feature_extraction_engine.handle_observation_recorded)
    bus.subscribe(FeaturesExtracted, feature_scoring_engine.handle_features_extracted)
    bus.subscribe(FeatureScoresCalculated, pattern_discovery_engine.handle_feature_scores_calculated)
    bus.subscribe(PatternsDiscovered, knowledge_engine.handle_patterns_discovered)

    # ------------------------------------------------------------------ Wire Part 1b
    bus.subscribe(MetricNormalized, objective_engine.handle_metric_normalized)
    bus.subscribe(SuccessScoreCalculated, performance_evaluation_engine.handle_success_score_calculated)

    # ------------------------------------------------------------------ Wire Part 2
    bus.subscribe(KnowledgeUpdated, confidence_engine.handle_knowledge_updated)
    bus.subscribe(KnowledgeUpdated, knowledge_coverage_engine.handle_knowledge_updated)
    bus.subscribe(ConfidenceUpdated, hypothesis_engine.handle_confidence_updated)
    bus.subscribe(HypothesisCreated, experiment_engine.handle_hypothesis_created)
    bus.subscribe(ExperimentCompleted, decision_engine.handle_experiment_completed)
    bus.subscribe(DecisionCreated, weekly_planning_engine.handle_decision_created)

    # --- Phase 4 Part 2 Wiring
    bus.subscribe(KnowledgeCoverageCalculated, opportunity_discovery_engine.handle_coverage_calculated)

    # ------------------------------------------------------------------ Wire Phase 4 Part 1
    bus.subscribe(FeaturesExtracted, hook_pattern_discovery_engine.handle_features_extracted)
    bus.subscribe(HookAnalyzed, hook_knowledge_engine.handle_hook_analyzed)

    # ------------------------------------------------------------------ Wire Phase 4 Part 2
    bus.subscribe(HookAnalyzed, hook_structure_learning_engine.handle_hook_analyzed)

    # ------------------------------------------------------------------ Wire Phase 5 Part 1
    # Phase5DecisionEngine subscribes ONLY to WeeklyStrategyCompleted.
    bus.subscribe(WeeklyStrategyCompleted, phase5_decision_engine.handle_weekly_strategy_completed)

    # ------------------------------------------------------------------ Wire Phase 6 Part 1
    # Phase6ExecutionEngine subscribes ONLY to DecisionCandidateApproved.
    bus.subscribe(DecisionCandidateApproved, phase6_execution_engine.handle_decision_candidate_approved)

    from core.container import container as _container
    _container.register("strategy_planning_engine", strategy_planning_engine)
    _container.register("phase5_decision_engine", phase5_decision_engine)
    _container.register("phase6_execution_engine", phase6_execution_engine)

    # ------------------------------------------------------------------ Notifications
    bus.subscribe(KnowledgeUpdated, notification_service.on_knowledge_updated)
    bus.subscribe(RuleActivated, notification_service.on_rule_activated)

    # ------------------------------------------------------------------ Cross-Phase Bridges
    # Wire Phase6 ExecutionCompleted → Phase7 Observation (lazy — avoids import cycles at startup)
    try:
        import phase7_observation as _p7  # noqa: F401 — ensures observation on sys.path
        from bridges.execution_to_observation import wire as _wire_exec_obs
        from observation.application.bootstrap import ApplicationBootstrap
        from observation.config import load_settings as _load_obs_settings
        _obs_bootstrap = ApplicationBootstrap(_load_obs_settings())
        _wire_exec_obs(bus, _obs_bootstrap)
    except Exception:
        import logging as _logging
        _logging.getLogger("core.wiring").warning(
            "Phase7 bridge not wired — observation package unavailable", exc_info=True
        )

    # Wire Phase10 Intelligence Core feedback → Phase5/6 event bus
    try:
        from bridges.intelligence_to_strategy import wire as _wire_intel_strat
        from phase10_intelligence.events.publisher import InMemoryEventPublisher as _P10Publisher
        _p10_publisher = _P10Publisher()
        _container.register("phase10_publisher", _p10_publisher)
        _wire_intel_strat(_p10_publisher, bus)
    except Exception:
        import logging as _logging
        _logging.getLogger("core.wiring").warning(
            "Phase10 feedback bridge not wired — intelligence package unavailable", exc_info=True
        )
