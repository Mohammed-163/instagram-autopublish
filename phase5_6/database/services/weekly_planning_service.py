from __future__ import annotations
import logging
from typing import List, Optional, Any, Dict
from datetime import datetime

from database.models import WeeklyPlan, StrategyHistory
from core.container import container
from core.events import WeeklyPlanCreated

logger = logging.getLogger(__name__)


class WeeklyPlanningService:
    def __init__(self, weekly_plans_repository=None, strategy_history_repository=None, event_bus=None) -> None:
        self.weekly_plans_repository = weekly_plans_repository or container.resolve("weekly_plans_repository")
        self.strategy_history_repository = strategy_history_repository or container.resolve("strategy_history_repository")
        self.event_bus = event_bus or container.resolve("event_bus")

    def create_plan(
        self,
        week_start: datetime,
        week_end: datetime,
        plan_data: Dict[str, Any],
        status: str = "draft",
        plan_id: Optional[Any] = None,
    ) -> WeeklyPlan:
        """
        Persist a weekly plan.
        plan_id: optional pre-generated UUID (used by WeeklyPlanningEngine so the
                 persisted record and the emitted event share the same ID).
        """
        # NOTE: the WeeklyPlan model's column is named `plan`, not `plan_data`.
        # The public parameter here stays `plan_data` (callers like
        # WeeklyPlanningEngine already use that name), but it must be mapped
        # to `plan` before hitting the repository/model, or SQLAlchemy raises
        # TypeError: 'plan_data' is an invalid keyword argument for WeeklyPlan.
        create_kwargs: Dict[str, Any] = dict(
            week_start_date=week_start,
            week_end_date=week_end,
            plan=plan_data,
            status=status,
        )
        if plan_id is not None:
            create_kwargs["id"] = plan_id
        plan = self.weekly_plans_repository.create(**create_kwargs)
        # Do NOT publish WeeklyPlanCreated here — the engine that called us
        # owns the event and will publish it with the full content_mix payload.
        return plan

    def activate_plan(self, plan_id: Any) -> Optional[WeeklyPlan]:
        current_active = self.weekly_plans_repository.get_active()
        if current_active is not None:
            self.weekly_plans_repository.update(current_active.id, status="superseded")
        return self.weekly_plans_repository.update(plan_id, status="active")

    def get_by_week_start(self, week_start_date):
        return self.weekly_plans_repository.get_by_week_start(week_start_date)

    def complete_plan(self, plan_id: Any) -> Optional[WeeklyPlan]:
        return self.weekly_plans_repository.update(plan_id, status="completed")

    def get_active_plan(self) -> Optional[WeeklyPlan]:
        return self.weekly_plans_repository.get_active()

    def get_plan_history(self, limit: int = 10) -> List[WeeklyPlan]:
        plans = self.weekly_plans_repository.list_all()
        return sorted(plans, key=lambda x: x.created_at, reverse=True)[:limit]

    def record_strategy_change(self, name: str, from_config: Dict[str, Any], to_config: Dict[str, Any], reason: str) -> StrategyHistory:
        return self.strategy_history_repository.create(
            strategy_name=name, from_config=from_config, to_config=to_config, reason=reason
        )


weekly_planning_service = WeeklyPlanningService()
