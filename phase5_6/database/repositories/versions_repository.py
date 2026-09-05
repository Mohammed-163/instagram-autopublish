from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select

from database.client import get_session
from database.models import ModelVersion, PromptVersion
from database.repositories.base_repository import BaseRepository


class PromptVersionsRepository(BaseRepository[PromptVersion]):
    model = PromptVersion

    def get_active(self, name: str) -> Optional[PromptVersion]:
        with get_session() as session:
            stmt = select(PromptVersion).where(PromptVersion.name == name, PromptVersion.is_active.is_(True))
            return session.scalars(stmt).first()

    def list_for_name(self, name: str) -> List[PromptVersion]:
        with get_session() as session:
            stmt = select(PromptVersion).where(PromptVersion.name == name)
            return list(session.scalars(stmt).all())


class ModelVersionsRepository(BaseRepository[ModelVersion]):
    model = ModelVersion

    def get_active(self, purpose: str) -> Optional[ModelVersion]:
        with get_session() as session:
            stmt = select(ModelVersion).where(ModelVersion.purpose == purpose, ModelVersion.is_active.is_(True))
            return session.scalars(stmt).first()


prompt_versions_repository = PromptVersionsRepository()
model_versions_repository = ModelVersionsRepository()
