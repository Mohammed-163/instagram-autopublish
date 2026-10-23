"""
Dependency Injection container.

Services must never construct their own repositories. Instead, a service
declares what it needs in its constructor and the container supplies the
real (database-backed) singleton by default:

    Engine -> Service -> Repository -> Database

In production code nothing changes: `post_service` etc. below are built by
the container with the real repositories, exactly like before. What changes
is that tests (or a future caller) can build any Service with a fake
repository instead, without touching Service code at all:

    fake_posts_repo = FakePostsRepository()
    service = PostService(posts_repository=fake_posts_repo)

This module is the single place that knows how to wire the real, default
graph of objects together.
"""
from __future__ import annotations

from typing import Any, Dict


class Container:
    """Minimal service locator. Not a framework — just a registry so
    default dependencies live in one place instead of being imported
    ad-hoc inside every service module."""

    def __init__(self) -> None:
        self._bindings: Dict[str, Any] = {}

    def register(self, name: str, instance: Any) -> None:
        self._bindings[name] = instance

    def resolve(self, name: str) -> Any:
        if name not in self._bindings:
            raise KeyError(f"No binding registered for '{name}'")
        return self._bindings[name]

    def has(self, name: str) -> bool:
        return name in self._bindings


# Process-wide default container. Created empty and populated in-place below,
# rather than being reassigned at the end of this module. This matters:
# several service modules do `from core.container import container` at
# import time (to resolve their default repositories). If `container` were
# only bound at the bottom of this file via `container = _build_default_container()`,
# any such import that happens *during* that call (container -> services/__init__.py
# -> knowledge_service -> "from core.container import container") would hit a
# partially-initialized module with no `container` attribute yet, and blow up
# with "cannot import name 'container' from partially initialized module".
# Binding the name immediately, then filling it in via .register(), means the
# object always exists by the time any nested import reaches back for it.
container = Container()


def _build_default_container(container: "Container") -> None:
    from core.event_bus import event_bus
    container.register("event_bus", event_bus)

    # ------------------------------------------------------------------ Repositories
    from database.repositories import (
        confidence_scores_repository,
        decision_logs_repository,
        designs_repository,
        engine_health_repository,
        events_repository,
        experiments_repository,
        explainability_repository,
        failures_repository,
        features_repository,
        history_repository,
        hook_patterns_repository,
        hook_statistics_repository,
        hook_structures_repository,
        hook_feature_values_repository,
        hook_feature_statistics_repository,
        hypotheses_repository,
        knowledge_rules_repository,
        knowledge_versions_repository,
        media_repository,
        memory_repository,
        metrics_repository,
        model_versions_repository,
        notifications_repository,
        opportunity_repository,
        opportunity_transition_repository,
        posts_repository,
        prompt_versions_repository,
        quality_results_repository,
        rule_lifecycle_events_repository,
        schedule_repository,
        scores_repository,
        settings_repository,
        strategy_candidates_repository,
        strategy_history_repository,
        topics_repository,
        weekly_plans_repository,
        weekly_strategy_versions_repository,
        knowledge_coverage_repository,
        decision_candidates_repository,
    )
    from database.repositories.execution_repository import (
        execution_repository,
        execution_transition_repository,
    )

    for name, repo in {
        "posts_repository": posts_repository,
        "topics_repository": topics_repository,
        "designs_repository": designs_repository,
        "media_repository": media_repository,
        "schedule_repository": schedule_repository,
        "history_repository": history_repository,
        "metrics_repository": metrics_repository,
        "features_repository": features_repository,
        "scores_repository": scores_repository,
        "knowledge_versions_repository": knowledge_versions_repository,
        "knowledge_rules_repository": knowledge_rules_repository,
        "rule_lifecycle_events_repository": rule_lifecycle_events_repository,
        "hypotheses_repository": hypotheses_repository,
        "experiments_repository": experiments_repository,
        "memory_repository": memory_repository,
        "weekly_plans_repository": weekly_plans_repository,
        "strategy_history_repository": strategy_history_repository,
        "decision_logs_repository": decision_logs_repository,
        "confidence_scores_repository": confidence_scores_repository,
        "quality_results_repository": quality_results_repository,
        "engine_health_repository": engine_health_repository,
        "notifications_repository": notifications_repository,
        "events_repository": events_repository,
        "settings_repository": settings_repository,
        "prompt_versions_repository": prompt_versions_repository,
        "model_versions_repository": model_versions_repository,
        "failures_repository": failures_repository,
        "explainability_repository": explainability_repository,
        "hook_patterns_repository": hook_patterns_repository,
        "hook_statistics_repository": hook_statistics_repository,
        "hook_structures_repository": hook_structures_repository,
        "hook_feature_values_repository": hook_feature_values_repository,
        "hook_feature_statistics_repository": hook_feature_statistics_repository,
        "knowledge_coverage_repository": knowledge_coverage_repository,
        "opportunity_repository": opportunity_repository,
        "opportunity_transition_repository": opportunity_transition_repository,
        "weekly_strategy_versions_repository": weekly_strategy_versions_repository,
        "strategy_candidates_repository": strategy_candidates_repository,
        "decision_candidates_repository": decision_candidates_repository,
        "execution_repository": execution_repository,
        "execution_transition_repository": execution_transition_repository,
    }.items():
        container.register(name, repo)

    # ------------------------------------------------------------------ Services
    # Register each service immediately after importing so that services
    # with inter-service dependencies (e.g. opportunity_scoring_service
    # needs settings_service already in container) always find their
    # dependencies registered at construction time.
    from database.services.settings_service import settings_service
    container.register("settings_service", settings_service)

    from database.services.audit_service import audit_service
    container.register("audit_service", audit_service)

    from database.services.confidence_service import confidence_service
    container.register("confidence_service", confidence_service)

    from database.services.decision_service import decision_service
    container.register("decision_service", decision_service)

    from database.services.engine_health_service import engine_health_service
    container.register("engine_health_service", engine_health_service)

    from database.services.experiment_service import experiment_service
    container.register("experiment_service", experiment_service)

    from database.services.feature_service import feature_service
    container.register("feature_service", feature_service)

    from database.services.hook_service import hook_service
    container.register("hook_service", hook_service)

    from database.services.hook_structure_service import hook_structure_service
    container.register("hook_structure_service", hook_structure_service)

    from database.services.hypothesis_service import hypothesis_service
    container.register("hypothesis_service", hypothesis_service)

    from database.services.knowledge_coverage_service import knowledge_coverage_service
    container.register("knowledge_coverage_service", knowledge_coverage_service)

    from database.services.knowledge_service import knowledge_service
    container.register("knowledge_service", knowledge_service)

    from database.services.metrics_service import metrics_service
    container.register("metrics_service", metrics_service)

    from database.services.memory_service import memory_service
    container.register("memory_service", memory_service)

    from database.services.notification_service import notification_service
    container.register("notification_service", notification_service)

    from database.services.opportunity_scoring_service import opportunity_scoring_service
    container.register("opportunity_scoring_service", opportunity_scoring_service)

    from database.services.opportunity_service import opportunity_service
    container.register("opportunity_service", opportunity_service)

    from database.services.post_service import post_service
    container.register("post_service", post_service)

    from database.services.quality_service import quality_service
    container.register("quality_service", quality_service)

    from database.services.scoring_service import scoring_service
    container.register("scoring_service", scoring_service)

    from database.services.strategy_service import strategy_service
    container.register("strategy_service", strategy_service)

    from database.services.weekly_planning_service import weekly_planning_service
    container.register("weekly_planning_service", weekly_planning_service)

    from database.services.decision_scoring_service import decision_scoring_service
    container.register("decision_scoring_service", decision_scoring_service)

    from database.services.phase5_decision_service import phase5_decision_service
    container.register("phase5_decision_service", phase5_decision_service)

    from database.services.execution_validation_service import execution_validation_service
    container.register("execution_validation_service", execution_validation_service)

    from database.services.phase6_execution_service import phase6_execution_service
    container.register("phase6_execution_service", phase6_execution_service)

    # ------------------------------------------------------------------ Phase 6 Part 2 — Orchestrator & Platform Abstraction
    from engines.execution.adapters.registry import adapter_registry
    from engines.execution.factory import execution_plan_factory
    from engines.execution.orchestrator import execution_orchestrator

    for name, obj in {
        "adapter_registry": adapter_registry,
        "execution_plan_factory": execution_plan_factory,
        "execution_orchestrator": execution_orchestrator,
    }.items():
        container.register(name, obj)

    # ------------------------------------------------------------------ Phase 6 Part 3 — Pipeline
    from engines.execution.pipeline.registry import stage_registry
    from engines.execution.pipeline.factory import execution_pipeline_factory

    for name, obj in {
        "stage_registry": stage_registry,
        "execution_pipeline_factory": execution_pipeline_factory,
    }.items():
        container.register(name, obj)

    # ------------------------------------------------------------------ Wire event subscriptions
    # All repos and services are registered; safe to wire engines to the bus.
    from core.wiring import wire_default_subscribers
    wire_default_subscribers()


# Engines and services fall back to `container` (defined above) when a
# dependency isn't explicitly injected (e.g. in unit tests inject fakes).
_build_default_container(container)
