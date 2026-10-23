"""
WeeklyPlanningEngine
====================
10) Weekly Planning Engine

Responsibility:
- Listen to DecisionCreated event.
- Generate next week's publishing plan based on validated decisions,
  knowledge rules, topics, and diversity rates.
- Persist the plan via WeeklyPlanningService (Service Layer).
- Emit WeeklyPlanCreated event.

Design:
- Extends EngineBase — all planning parameters (posting slots, diversity index,
  min posts, recommended formats) from EngineSettingsReader.
- Depends on WeeklyPlanningService and KnowledgeService — never on repositories.
- Does NOT use LLM/AI for algorithmic scheduling or rule building.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from core.events import DecisionCreated, WeeklyPlanCreated
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)


class WeeklyPlanningEngine(EngineBase):
    """
    Converts DecisionCreated → WeeklyPlanCreated.
    All configurable planning parameters come from EngineSettingsReader.
    """

    ENGINE_NAME = "weekly_planning"

    def __init__(
        self,
        event_bus: Any,
        weekly_planning_service: Any,
        knowledge_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.weekly_planning_service = weekly_planning_service
        self.knowledge_service = knowledge_service

    def handle_decision_created(self, event: DecisionCreated) -> None:
        """Handle DecisionCreated: generate next week's plan and emit WeeklyPlanCreated."""
        try:
            decision_id = event.decision_id
            logger.info(
                "[WeeklyPlanningEngine] Generating weekly plan following Decision %s", decision_id
            )

            cfg = self.settings

            # Fetch top topics via KnowledgeService (wraps topics_repository)
            topic_names = self.knowledge_service.get_top_topic_names(limit=5)

            # Fetch active rule IDs via KnowledgeService
            active_rules = self.knowledge_service.get_active_rules()
            rule_ids = [str(getattr(r, "id", uuid.uuid4())) for r in active_rules]

            target_posts_count = max(cfg.planning_min_posts, len(topic_names) * 2)

            content_mix = {
                "topics": topic_names,
                "applied_decision_id": str(decision_id),
                "applied_rules": rule_ids,
                "optimal_posting_slots": cfg.planning_posting_slots,
                "diversity_index": cfg.planning_diversity_index,
                "recommended_formats": cfg.planning_recommended_formats,
            }

            # Persist via WeeklyPlanningService
            plan_id = uuid.uuid4()
            dt_start = datetime.now(timezone.utc)

            self.weekly_planning_service.create_plan(
                plan_id=plan_id,
                week_start=dt_start,
                week_end=dt_start,
                plan_data=content_mix,
                status="draft",
            )

            # Emit WeeklyPlanCreated
            plan_event = WeeklyPlanCreated(
                plan_id=plan_id,
                status="draft",
                target_posts=target_posts_count,
                content_mix=content_mix,
            )
            self.event_bus.publish(plan_event)

            self.heartbeat("healthy")
            logger.info("[WeeklyPlanningEngine] WeeklyPlanCreated published: %s", plan_id)

        except Exception as e:
            logger.exception("[WeeklyPlanningEngine] Error generating weekly plan: %s", e)
            self.heartbeat("error", error=str(e))
