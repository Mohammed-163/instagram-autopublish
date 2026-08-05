from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from database.models import StrategyCandidate, WeeklyStrategyVersion
from core.container import container

logger = logging.getLogger(__name__)


class StrategyService:
    """Service-layer facade over weekly_strategy_versions / strategy_candidates.
    Also records explainability notes for the overall version via the shared
    ExplainabilityRepository. Engines depend on this — never on repositories."""

    def __init__(
        self,
        weekly_strategy_versions_repository=None,
        strategy_candidates_repository=None,
        explainability_repository=None,
    ) -> None:
        self.weekly_strategy_versions_repository = (
            weekly_strategy_versions_repository or container.resolve("weekly_strategy_versions_repository")
        )
        self.strategy_candidates_repository = (
            strategy_candidates_repository or container.resolve("strategy_candidates_repository")
        )
        self.explainability_repository = (
            explainability_repository or container.resolve("explainability_repository")
        )

    # ------------------------------------------------------------------ versions
    def next_version_number(self) -> int:
        return self.weekly_strategy_versions_repository.next_version_number()

    def create_version(self, week_start: date, week_end: date, summary: str = "") -> WeeklyStrategyVersion:
        version_number = self.next_version_number()
        return self.weekly_strategy_versions_repository.create(
            version_number=version_number,
            week_start=week_start,
            week_end=week_end,
            status="planned",
            summary=summary,
        )

    def complete_version(self, version_id: Any, summary: Optional[str] = None) -> Optional[WeeklyStrategyVersion]:
        fields: Dict[str, Any] = {}
        if summary is not None:
            fields["summary"] = summary
        return self.weekly_strategy_versions_repository.update(version_id, **fields) if fields else \
            self.weekly_strategy_versions_repository.get_by_id(version_id)

    def get_recent_versions(self, limit: int = 10) -> List[WeeklyStrategyVersion]:
        return self.weekly_strategy_versions_repository.list_recent(limit=limit)

    def get_latest_version(self) -> Optional[WeeklyStrategyVersion]:
        return self.weekly_strategy_versions_repository.get_latest()

    # ------------------------------------------------------------------ candidates
    def add_candidate(
        self,
        strategy_version_id: Any,
        position: int,
        category: str,
        topic: str,
        hook_type: str,
        objective: str,
        reason: str,
        confidence: float,
        expected_success: float,
        is_experiment: bool,
        based_on: Optional[Dict[str, Any]] = None,
    ) -> StrategyCandidate:
        return self.strategy_candidates_repository.create(
            strategy_version_id=strategy_version_id,
            position=position,
            category=category,
            topic=topic,
            hook_type=hook_type,
            objective=objective,
            reason=reason,
            confidence=confidence,
            expected_success=expected_success,
            is_experiment=is_experiment,
            based_on=based_on or {},
        )

    def get_candidates_for_version(self, strategy_version_id: Any) -> List[StrategyCandidate]:
        return self.strategy_candidates_repository.list_for_version(strategy_version_id)

    def get_recent_candidates(self, limit_versions: int = 4) -> List[StrategyCandidate]:
        """Flatten candidates across the most recent N versions — used by
        the planning engine's diversity/anti-repetition checks."""
        versions = self.get_recent_versions(limit=limit_versions)
        candidates: List[StrategyCandidate] = []
        for v in versions:
            candidates.extend(self.get_candidates_for_version(v.id))
        return candidates

    # ------------------------------------------------------------------ explainability
    def record_explanation(self, subject_id: Any, explanation: str, factors: Optional[Dict[str, Any]] = None) -> None:
        self.explainability_repository.create(
            subject_type="weekly_strategy_version",
            subject_id=subject_id,
            explanation=explanation,
            factors=factors or {},
        )


strategy_service = StrategyService()
