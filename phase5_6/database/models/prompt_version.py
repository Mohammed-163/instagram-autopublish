from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class PromptVersion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Every prompt template used to generate content, versioned so the
    Decision Engine's "build a dynamic prompt" step (per the project
    charter) can be traced back to exactly which template/version produced
    a given post, via posts.prompt_version."""

    __tablename__ = "prompt_versions"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[Optional[dict]] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
