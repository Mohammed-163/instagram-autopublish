from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, UUIDPrimaryKeyMixin


class RuleLifecycleEvent(UUIDPrimaryKeyMixin, Base):
    """Audit trail entry for every state transition of a knowledge_rule
    (proposed -> active -> suspended -> retired), with the reason why."""

    __tablename__ = "rule_lifecycle_events"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_rules.id", ondelete="CASCADE"), nullable=False
    )
    from_state: Mapped[Optional[str]] = mapped_column(Text)
    to_state: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    rule: Mapped["KnowledgeRule"] = relationship(back_populates="lifecycle_events")  # noqa: F821
