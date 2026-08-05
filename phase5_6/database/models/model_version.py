from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class ModelVersion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Every AI model/provider version used anywhere in the pipeline (e.g.
    Gemini for text classification per the project charter). Lets future
    analysis separate 'the model changed' from 'the strategy changed' when
    explaining a shift in results."""

    __tablename__ = "model_versions"

    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[Optional[str]] = mapped_column(Text)
    purpose: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
