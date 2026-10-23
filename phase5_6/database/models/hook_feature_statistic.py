from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, UUIDPrimaryKeyMixin, UpdatedAtMixin


class HookFeatureStatistic(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
    """Foundation table for Hook Feature Importance (Phase 4 Part 3 —
    Opportunity Discovery). Schema and service contract (see
    HookStructureService.record_feature_observation) are finalized now so
    that phase does not require a migration/redesign, but nothing in this
    phase writes to it yet: computing a feature's real contribution to
    success requires the post's success score, which only exists
    downstream (ObjectiveEngine / ScoringService), after this engine has
    already run.
    """

    __tablename__ = "hook_feature_statistics"
    __table_args__ = (
        UniqueConstraint(
            "category", "hook_type", "feature_name",
            name="uq_hook_feature_statistics_category_hook_type_feature",
        ),
    )

    category: Mapped[str] = mapped_column(Text, nullable=False)
    hook_type: Mapped[str] = mapped_column(Text, nullable=False)
    feature_name: Mapped[str] = mapped_column(Text, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    contribution_sum: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0"))
    avg_contribution: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0"))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0"))
