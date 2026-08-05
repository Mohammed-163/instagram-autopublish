from __future__ import annotations
"""
Service layer package for Phase 5/6.

Services are NOT eagerly imported here to avoid circular import chains:
  database.services.__init__
    -> service modules (from core.container import container)
    -> core.container (_build_default_container)
    -> database.services.<submodule>  [circular!]

All wiring is triggered at the end of core.container._build_default_container.
Individual consumers import services directly from their submodules.
Re-exports below are populated lazily via __getattr__ so that
  `from database.services import knowledge_service`
still works.
"""

__all__ = [
    "audit_service",
    "confidence_service",
    "decision_service",
    "decision_scoring_service",
    "engine_health_service",
    "execution_validation_service",
    "experiment_service",
    "feature_service",
    "hook_service",
    "hook_structure_service",
    "hypothesis_service",
    "knowledge_coverage_service",
    "knowledge_service",
    "memory_service",
    "metrics_service",
    "notification_service",
    "opportunity_scoring_service",
    "opportunity_service",
    "phase5_decision_service",
    "phase6_execution_service",
    "post_service",
    "quality_service",
    "scoring_service",
    "settings_service",
    "strategy_service",
    "weekly_planning_service",
]

_SERVICE_MODULES = {
    "audit_service": "database.services.audit_service",
    "confidence_service": "database.services.confidence_service",
    "decision_service": "database.services.decision_service",
    "decision_scoring_service": "database.services.decision_scoring_service",
    "engine_health_service": "database.services.engine_health_service",
    "execution_validation_service": "database.services.execution_validation_service",
    "experiment_service": "database.services.experiment_service",
    "feature_service": "database.services.feature_service",
    "hook_service": "database.services.hook_service",
    "hook_structure_service": "database.services.hook_structure_service",
    "hypothesis_service": "database.services.hypothesis_service",
    "knowledge_coverage_service": "database.services.knowledge_coverage_service",
    "knowledge_service": "database.services.knowledge_service",
    "memory_service": "database.services.memory_service",
    "metrics_service": "database.services.metrics_service",
    "notification_service": "database.services.notification_service",
    "opportunity_scoring_service": "database.services.opportunity_scoring_service",
    "opportunity_service": "database.services.opportunity_service",
    "phase5_decision_service": "database.services.phase5_decision_service",
    "phase6_execution_service": "database.services.phase6_execution_service",
    "post_service": "database.services.post_service",
    "quality_service": "database.services.quality_service",
    "scoring_service": "database.services.scoring_service",
    "settings_service": "database.services.settings_service",
    "strategy_service": "database.services.strategy_service",
    "weekly_planning_service": "database.services.weekly_planning_service",
}


def __getattr__(name: str):
    if name in _SERVICE_MODULES:
        import importlib
        module = importlib.import_module(_SERVICE_MODULES[name])
        obj = getattr(module, name)
        # Cache in module globals so subsequent access is O(1)
        import sys
        setattr(sys.modules[__name__], name, obj)
        return obj
    raise AttributeError(f"module 'database.services' has no attribute {name!r}")
