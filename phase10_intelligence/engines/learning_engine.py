"""
LearningEngine

Engines ORCHESTRATE ONLY: they sequence calls across services and repositories
and never contain business rules, thresholds, or scoring formulas themselves.
"""
from __future__ import annotations

from ..domain.models import ConfidenceCalibration, FeedbackRecord
from ..services.confidence_calibration_service import ConfidenceCalibrationService
from ..services.decision_feedback_service import DecisionFeedbackService
from ..services.self_improvement_service import SelfImprovementService


class LearningEngine:
    """Orchestrates the decision-feedback -> calibration -> self-improvement loop."""

    def __init__(self, feedback_service: DecisionFeedbackService,
                 calibration_service: ConfidenceCalibrationService,
                 self_improvement_service: SelfImprovementService) -> None:
        self._feedback_service = feedback_service
        self._calibration_service = calibration_service
        self._self_improvement_service = self_improvement_service

    def close_loop(self, subject_type: str, subject_key: str, raw_confidence: float,
                    outcome_score: float, sample_size: int) -> tuple[FeedbackRecord, ConfidenceCalibration, dict]:
        feedback = self._feedback_service.apply_feedback(subject_type, subject_key, outcome_score)
        calibration = self._calibration_service.calibrate(
            subject_type, subject_key, raw_confidence, outcome_score, sample_size
        )
        review = self._self_improvement_service.review_recent_performance()
        return feedback, calibration, review
