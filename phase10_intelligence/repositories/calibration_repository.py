"""
CalibrationRepository

Repository responsibility: persistence ONLY. No business rules,
thresholds, or scoring logic may appear here -- that belongs in services.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from ..domain.models import ConfidenceCalibration
from ..orm.models import ConfidenceCalibrationORM


class CalibrationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, calibration: ConfidenceCalibration) -> ConfidenceCalibration:
        row = ConfidenceCalibrationORM(
            subject_type=calibration.subject_type, subject_key=calibration.subject_key,
            raw_confidence=calibration.raw_confidence,
            calibrated_confidence=calibration.calibrated_confidence,
            sample_size=calibration.sample_size, fingerprint=calibration.fingerprint,
            version=calibration.version,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def latest_for_subject(self, subject_type: str, subject_key: str) -> Optional[ConfidenceCalibration]:
        row = (
            self._session.query(ConfidenceCalibrationORM)
            .filter_by(subject_type=subject_type, subject_key=subject_key)
            .order_by(ConfidenceCalibrationORM.id.desc())
            .first()
        )
        return self._to_domain(row) if row else None

    def list_for_subject(self, subject_type: str, subject_key: str) -> List[ConfidenceCalibration]:
        rows = (
            self._session.query(ConfidenceCalibrationORM)
            .filter_by(subject_type=subject_type, subject_key=subject_key)
            .all()
        )
        return [self._to_domain(r) for r in rows]

    @staticmethod
    def _to_domain(row: ConfidenceCalibrationORM) -> ConfidenceCalibration:
        return ConfidenceCalibration(
            id=row.id, subject_type=row.subject_type, subject_key=row.subject_key,
            raw_confidence=row.raw_confidence, calibrated_confidence=row.calibrated_confidence,
            sample_size=row.sample_size, fingerprint=row.fingerprint, version=row.version,
        )
