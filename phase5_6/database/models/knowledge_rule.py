from __future__ import annotations

import uuid
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, UpdatedAtMixin

LIFECYCLE_STATES = ("proposed", "active", "suspended", "retired")


class KnowledgeRule(UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    """An executable rule produced by the (future) learning loop:
    conditions -> action, with a weight/confidence and a lifecycle state.
    This is the 'knowledge' the Decision Engine will read at generation
    time. Written here now only as structure; nothing populates it yet."""

    __tablename__ = "knowledge_rules"

    knowledge_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_versions.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    action: Mapped[dict] = mapped_column(JSONB, nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("1.0"))
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    lifecycle_state: Mapped[str] = mapped_column(Text, default="proposed")

    knowledge_version: Mapped[Optional["KnowledgeVersion"]] = relationship(back_populates="rules")  # noqa: F821
    lifecycle_events: Mapped[List["RuleLifecycleEvent"]] = relationship(  # noqa: F821
        back_populates="rule", cascade="all, delete-orphan"
    )
