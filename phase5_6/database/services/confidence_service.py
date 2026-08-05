from __future__ import annotations
import logging
from typing import List, Optional, Any, Dict

from database.models import ConfidenceScore
from core.container import container

logger = logging.getLogger(__name__)


class ConfidenceService:
    def __init__(self, confidence_scores_repository=None) -> None:
        self.confidence_scores_repository = confidence_scores_repository or container.resolve("confidence_scores_repository")

    def score(self, subject_type: str, subject_id: Any, score_value: float, method: Optional[str] = None) -> ConfidenceScore:
        return self.confidence_scores_repository.create(
            subject_type=subject_type, subject_id=subject_id, score_value=score_value, method=method
        )

    def get_latest(self, subject_type: str, subject_id: Any) -> Optional[ConfidenceScore]:
        return self.confidence_scores_repository.latest_for_subject(subject_type, subject_id)

    def get_score_history(self, subject_type: str, subject_id: Any, limit: int = 10) -> List[ConfidenceScore]:
        latest = self.confidence_scores_repository.latest_for_subject(subject_type, subject_id)
        return [latest][:limit] if latest else []

    def record_score(
        self,
        rule_id: Any,
        confidence_score: float,
        sample_size: int = 0,
    ) -> None:
        """
        Persist a confidence score for a knowledge rule.
        Used by ConfidenceEngine after each rule evaluation.
        """
        try:
            self.confidence_scores_repository.create(
                rule_id=rule_id,
                confidence_score=confidence_score,
                sample_size=sample_size,
            )
            logger.debug(
                "[ConfidenceService] Recorded score=%.4f for rule %s", confidence_score, rule_id
            )
        except Exception:
            logger.exception(
                "[ConfidenceService] Failed to persist confidence score for rule %s", rule_id
            )


confidence_service = ConfidenceService()
