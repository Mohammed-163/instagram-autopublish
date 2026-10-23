"""
SQLAlchemy ORM models for persistence. These are storage shapes only —
no business logic lives here. Mapping between ORM rows and domain
objects happens exclusively in the repository layer.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class KnowledgeCoverageORM(Base):
    """Persisted representation of a KnowledgeCoverage result."""

    __tablename__ = "knowledge_coverage"

    coverage_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    knowledge_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    coverage_profile_id: Mapped[str] = mapped_column(String(64), nullable=False)
    coverage_profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    coverage_profile_description: Mapped[str] = mapped_column(Text, default="")
    coverage_profile_metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    coverage_score: Mapped[float] = mapped_column(Float, nullable=False)
    coverage_confidence: Mapped[float] = mapped_column(Float, nullable=False)

    coverage_dimensions_json: Mapped[str] = mapped_column(Text, nullable=False)
    detected_gaps_json: Mapped[str] = mapped_column(Text, nullable=False)

    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    structural_fingerprint: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    feature_fingerprint: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    fingerprint_hash: Mapped[str] = mapped_column(String(64), index=True, unique=True, nullable=False)
    fingerprint_version: Mapped[str] = mapped_column(String(32), nullable=False)

    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)

    versions_json: Mapped[str] = mapped_column(Text, nullable=False)
    explainability_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    transitions: Mapped[list["CoverageTransitionORM"]] = relationship(
        back_populates="coverage",
        foreign_keys="CoverageTransitionORM.coverage_id",
        cascade="all, delete-orphan",
    )


class CoverageTransitionORM(Base):
    """
    Records a transition from one coverage result to a superseding one
    for the same knowledge_id. Used for audit/history, not for
    recomputation.
    """

    __tablename__ = "coverage_transition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    coverage_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("knowledge_coverage.coverage_id"), nullable=False
    )
    previous_coverage_id: Mapped[str] = mapped_column(String(64), nullable=True)
    knowledge_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    previous_score: Mapped[float] = mapped_column(Float, nullable=True)
    new_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    coverage: Mapped["KnowledgeCoverageORM"] = relationship(
        back_populates="transitions", foreign_keys=[coverage_id]
    )
