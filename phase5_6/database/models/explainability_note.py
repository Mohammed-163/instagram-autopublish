from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, UUIDPrimaryKeyMixin


class ExplainabilityNote(UUIDPrimaryKeyMixin, Base):
    """Human-readable 'why' attached to any subject (a decision_log, a
    knowledge_rule, a weekly_plan...) via (subject_type, subject_id).
    Separate from decision_logs.reasoning because not every explainable
    subject is a decision (e.g. explaining a whole weekly_plan at once)."""

    __tablename__ = "explainability_notes"

    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    factors: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
