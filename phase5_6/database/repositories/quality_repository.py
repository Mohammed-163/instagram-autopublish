from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import select

from database.client import get_session
from database.models import QualityResult
from database.repositories.base_repository import BaseRepository


class QualityResultsRepository(BaseRepository[QualityResult]):
    model = QualityResult

    def list_for_post(self, post_id: uuid.UUID) -> List[QualityResult]:
        with get_session() as session:
            stmt = select(QualityResult).where(QualityResult.post_id == post_id).order_by(
                QualityResult.checked_at.desc()
            )
            return list(session.scalars(stmt).all())

    def latest_passed(self, post_id: uuid.UUID, gate_name: str) -> bool:
        with get_session() as session:
            stmt = select(QualityResult).where(
                QualityResult.post_id == post_id, QualityResult.gate_name == gate_name
            ).order_by(QualityResult.checked_at.desc())
            result = session.scalars(stmt).first()
            return bool(result and result.passed)


quality_results_repository = QualityResultsRepository()
