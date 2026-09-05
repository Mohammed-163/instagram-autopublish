from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

HOOK_TYPES = (
    "curiosity", "shock", "question", "comparison", "warning", "myth",
    "hidden_fact", "number", "before_after", "impossible", "contradiction",
    "psychology", "history", "science", "body",
)


class HookPattern(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One row per analyzed hook: the first line of a post's text, its
    extracted linguistic features, and the hook type it was classified as.
    Written by the Hook Pattern Discovery engine; never mutated afterwards
    (append-only, replayable)."""

    __tablename__ = "hook_patterns"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[Optional[str]] = mapped_column(Text)
    hook_text: Mapped[str] = mapped_column(Text, nullable=False)
    hook_type: Mapped[str] = mapped_column(Text, nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False)
