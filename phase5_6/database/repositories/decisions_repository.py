from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import select

from database.client import get_session
from database.models import ConfidenceScore, DecisionLog
from database.repositories.base_repository import BaseRepository


class DecisionLogsRepository(BaseRepository[DecisionLog]):
    model = DecisionLog

    def list_for_post(self, post_id: uuid.UUID) -> List[DecisionLog]:
        with get_session() as session:
            stmt = select(DecisionLog).where(DecisionLog.related_post_id == post_id)
            return list(session.scalars(stmt).all())

    def list_by_type(self, decision_type: str, limit: int = 200) -> List[DecisionLog]:
        with get_session() as session:
            stmt = select(DecisionLog).where(DecisionLog.decision_type == decision_type).order_by(
                DecisionLog.created_at.desc()
            ).limit(limit)
            return list(session.scalars(stmt).all())


class ConfidenceScoresRepository(BaseRepository[ConfidenceScore]):
    model = ConfidenceScore

    def latest_for_subject(self, subject_type: str, subject_id: uuid.UUID):
        with get_session() as session:
            stmt = select(ConfidenceScore).where(
                ConfidenceScore.subject_type == subject_type,
                ConfidenceScore.subject_id == subject_id,
            ).order_by(ConfidenceScore.computed_at.desc())
            return session.scalars(stmt).first()


decision_logs_repository = DecisionLogsRepository()
confidence_scores_repository = ConfidenceScoresRepository()
