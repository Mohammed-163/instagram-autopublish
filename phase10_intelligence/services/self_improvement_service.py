"""
SelfImprovementService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from typing import List

from ..config.settings import Settings
from ..domain.models import FeedbackRecord
from ..repositories.feedback_repository import FeedbackRepository


class SelfImprovementService:
    """
    Reviews recent feedback within a bounded window and reports whether the
    sample is large enough to draw a self-improvement conclusion, plus the
    mean outcome score for that window.
    """

    def __init__(self, repository: FeedbackRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    def review_recent_performance(self) -> dict:
        recent: List[FeedbackRecord] = self._repository.list_recent(
            self._settings.self_improvement_review_window
        )
        sufficient = len(recent) >= self._settings.self_improvement_min_sample_size
        mean_outcome = round(sum(r.outcome_score for r in recent) / len(recent), 10) if recent else 0.0
        return {
            "sample_size": len(recent),
            "sufficient_sample": sufficient,
            "mean_outcome_score": mean_outcome,
        }
