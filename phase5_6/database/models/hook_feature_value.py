from __future__ import annotations

import uuid
from typing import Any, Dict

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class HookFeatureValue(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One append-only row per (hook_structure, feature). This is the
    granular Explainability record: what value was extracted, how, from
    what source, and by which analyzer version — independent of the
    aggregate `features` JSONB blob on HookStructure, so individual
    features can be queried, audited, or replayed without touching the
    other features of the same hook.
    """

    __tablename__ = "hook_feature_values"

    hook_structure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hook_structures.id", ondelete="CASCADE"), nullable=False
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    feature_name: Mapped[str] = mapped_column(Text, nullable=False)
    feature_value: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    extraction_method: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, default="hook_text")
    analyzer_version: Mapped[str] = mapped_column(Text, nullable=False)
