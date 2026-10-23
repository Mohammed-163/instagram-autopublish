from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import select

from database.client import get_session
from database.models import ExplainabilityNote
from database.repositories.base_repository import BaseRepository


class ExplainabilityRepository(BaseRepository[ExplainabilityNote]):
    model = ExplainabilityNote

    def list_for_subject(self, subject_type: str, subject_id: uuid.UUID) -> List[ExplainabilityNote]:
        with get_session() as session:
            stmt = select(ExplainabilityNote).where(
                ExplainabilityNote.subject_type == subject_type,
                ExplainabilityNote.subject_id == subject_id,
            ).order_by(ExplainabilityNote.created_at.desc())
            return list(session.scalars(stmt).all())


explainability_repository = ExplainabilityRepository()
