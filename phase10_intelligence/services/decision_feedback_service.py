"""
DecisionFeedbackService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from ..config.settings import Settings
from ..domain.models import FeedbackRecord
from ..events import EventPublisher, FeedbackApplied
from ..fingerprint import compute_fingerprint
from ..repositories.feedback_repository import FeedbackRepository


class DecisionFeedbackService:
    """Closes the loop between decision outcomes and future calibration inputs."""

    def __init__(self, repository: FeedbackRepository, settings: Settings,
                 publisher: EventPublisher) -> None:
        self._repository = repository
        self._settings = settings
        self._publisher = publisher

    def apply_feedback(self, subject_type: str, subject_key: str, outcome_score: float) -> FeedbackRecord:
        learning_rate = self._settings.feedback_loop_learning_rate

        payload = {
            "subject_type": subject_type, "subject_key": subject_key,
            "outcome_score": outcome_score, "applied_learning_rate": learning_rate,
        }
        fp = compute_fingerprint(payload)

        record = FeedbackRecord(
            id=None, subject_type=subject_type, subject_key=subject_key,
            outcome_score=outcome_score, applied_learning_rate=learning_rate, fingerprint=fp,
        )
        stored = self._repository.add(record)

        self._publisher.publish(FeedbackApplied(
            subject_key=subject_key, fingerprint=stored.fingerprint,
            payload={"outcome_score": outcome_score},
        ))
        return stored
