"""
Generic repository base class.

Every table-specific repository extends this. Application code (scripts/,
lib/) must never import sqlalchemy or database.client directly — only
`database.repositories.*`.
"""
from __future__ import annotations

import uuid
from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.client import get_session
from database.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: Type[ModelT]

    def get_by_id(self, record_id: uuid.UUID) -> Optional[ModelT]:
        with get_session() as session:
            return session.get(self.model, record_id)

    def list_all(self, limit: int = 200) -> List[ModelT]:
        with get_session() as session:
            stmt = select(self.model).limit(limit)
            return list(session.scalars(stmt).all())

    def create(self, **fields) -> ModelT:
        with get_session() as session:
            obj = self.model(**fields)
            session.add(obj)
            session.flush()
            session.refresh(obj)
            return obj

    def update(self, record_id: uuid.UUID, **fields) -> Optional[ModelT]:
        with get_session() as session:
            obj = session.get(self.model, record_id)
            if obj is None:
                return None
            for key, value in fields.items():
                setattr(obj, key, value)
            session.flush()
            session.refresh(obj)
            return obj

    def delete(self, record_id: uuid.UUID) -> bool:
        with get_session() as session:
            obj = session.get(self.model, record_id)
            if obj is None:
                return False
            session.delete(obj)
            return True

    def _session(self) -> Session:
        """Escape hatch for repositories that need multi-statement /
        multi-table transactions. Prefer get_session() context manager."""
        from database.client import get_session_factory
        return get_session_factory()()
