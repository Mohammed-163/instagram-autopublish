"""
ConfidenceCalibrationService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from ..config.settings import Settings
from ..domain.models import ConfidenceCalibration
from ..events import ConfidenceCalibrated, EventPublisher
from ..fingerprint import compute_fingerprint
from ..repositories.calibration_repository import CalibrationRepository


class ConfidenceCalibrationService:
    """
    Calibrates a raw confidence score toward observed outcome rates using
    an exponential-smoothing update, entirely driven by Settings.
    """

    def __init__(self, repository: CalibrationRepository, settings: Settings,
                 publisher: EventPublisher) -> None:
        self._repository = repository
        self._settings = settings
        self._publisher = publisher

    def calibrate(self, subject_type: str, subject_key: str, raw_confidence: float,
                  observed_outcome_rate: float, sample_size: int) -> ConfidenceCalibration:
        alpha = self._settings.calibration_smoothing_factor
        calibrated = round(
            raw_confidence * (1 - alpha) + observed_outcome_rate * alpha, 10
        )

        payload = {
            "subject_type": subject_type, "subject_key": subject_key,
            "raw_confidence": raw_confidence, "calibrated_confidence": calibrated,
            "sample_size": sample_size,
        }
        fp = compute_fingerprint(payload)

        calibration = ConfidenceCalibration(
            id=None, subject_type=subject_type, subject_key=subject_key,
            raw_confidence=raw_confidence, calibrated_confidence=calibrated,
            sample_size=sample_size, fingerprint=fp,
        )
        stored = self._repository.add(calibration)

        self._publisher.publish(ConfidenceCalibrated(
            subject_key=subject_key, fingerprint=stored.fingerprint,
            payload={"calibrated_confidence": calibrated},
        ))
        return stored

    def is_high_confidence(self, calibration: ConfidenceCalibration) -> bool:
        return calibration.calibrated_confidence >= self._settings.high_confidence_threshold

    def meets_minimum(self, calibration: ConfidenceCalibration) -> bool:
        return calibration.calibrated_confidence >= self._settings.min_confidence_threshold
