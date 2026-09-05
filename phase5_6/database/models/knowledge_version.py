from __future__ import annotations

from typing import List, Optional

from sqlalchemy import Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class KnowledgeVersion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """An immutable snapshot marker of 'what the system believed' at a point
    in time. knowledge_rules point back to the version that produced them."""

    __tablename__ = "knowledge_versions"

    version_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

    rules: Mapped[List["KnowledgeRule"]] = relationship(back_populates="knowledge_version")  # noqa: F821
