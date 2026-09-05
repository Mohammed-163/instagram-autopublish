from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select

from database.client import get_session
from database.models import KnowledgeCoverageSnapshot
from database.repositories.base_repository import BaseRepository


class KnowledgeCoverageRepository(BaseRepository[KnowledgeCoverageSnapshot]):
    model = KnowledgeCoverageSnapshot

    def get_latest(self) -> Optional[KnowledgeCoverageSnapshot]:
        with get_session() as session:
            stmt = select(KnowledgeCoverageSnapshot).order_by(KnowledgeCoverageSnapshot.calculated_at.desc()).limit(1)
            return session.scalars(stmt).first()
    
    def get_by_version(self, coverage_version: str) -> Optional[KnowledgeCoverageSnapshot]:
        with get_session() as session:
            stmt = select(KnowledgeCoverageSnapshot).where(KnowledgeCoverageSnapshot.coverage_version == coverage_version)
            return session.scalars(stmt).first()

    def get_previous(self, before_id: uuid.UUID) -> Optional[KnowledgeCoverageSnapshot]:
        with get_session() as session:
            current = session.get(KnowledgeCoverageSnapshot, before_id)
            if not current:
                return None
            stmt = (
                select(KnowledgeCoverageSnapshot)
                .where(KnowledgeCoverageSnapshot.calculated_at < current.calculated_at)
                .order_by(KnowledgeCoverageSnapshot.calculated_at.desc())
                .limit(1)
            )
            return session.scalars(stmt).first()

knowledge_coverage_repository = KnowledgeCoverageRepository()
