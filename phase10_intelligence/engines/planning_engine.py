"""
PlanningEngine

Engines ORCHESTRATE ONLY: they sequence calls across services and repositories
and never contain business rules, thresholds, or scoring formulas themselves.
"""
from __future__ import annotations

from typing import List

from ..domain.models import PlanningCycle, Strategy
from ..services.adaptive_planning_service import AdaptivePlanningService
from ..services.knowledge_utilization_service import KnowledgeUtilizationService


class PlanningEngine:
    """Orchestrates knowledge lookup followed by adaptive cycle planning."""

    def __init__(self, planning_service: AdaptivePlanningService,
                 knowledge_service: KnowledgeUtilizationService) -> None:
        self._planning_service = planning_service
        self._knowledge_service = knowledge_service

    def plan_next_cycle(self, candidate_strategies: List[Strategy], subject_type: str) -> PlanningCycle:
        # Knowledge utilization informs, but does not itself decide, the plan.
        self._knowledge_service.relevant_knowledge(subject_type)
        return self._planning_service.plan_cycle(candidate_strategies)
