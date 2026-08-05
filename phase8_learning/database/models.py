"""
SQLAlchemy models for the Learning Layer.

Tables:
    knowledge              - current + historical knowledge rows
    knowledge_versions     - version history for each knowledge_id lineage
    knowledge_transitions  - status transitions (e.g. CANDIDATE -> VALIDATED -> ACTIVE)
    knowledge_evidence     - evidence rows linked to a knowledge row
    knowledge_patterns     - pattern rows linked to a knowledge row (1:1 in practice,
                              modeled as its own table for extensibility/auditability)

No business logic lives here. This module only defines storage shape.
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class KnowledgeModel(Base):
    __tablename__ = "knowledge"

    knowledge_id = Column(String(64), primary_key=True)
    title = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False)

    fingerprint_hash = Column(String(64), nullable=False, index=True)
    structural_fingerprint = Column(String(64), nullable=False)
    feature_fingerprint = Column(String(64), nullable=False)

    knowledge_version = Column(Integer, nullable=False)
    fingerprint_version = Column(String(32), nullable=False)
    engine_version = Column(String(32), nullable=False)
    schema_version = Column(String(32), nullable=False)

    confidence_score = Column(Float, nullable=False)
    confidence_sample_size = Column(Integer, nullable=False)
    confidence_consistency = Column(Float, nullable=False)
    confidence_components = Column(JSON, nullable=False, default=dict)

    explainability = Column(JSON, nullable=False)

    previous_knowledge_id = Column(
        String(64), ForeignKey("knowledge.knowledge_id"), nullable=True
    )

    evidence = relationship(
        "KnowledgeEvidenceModel",
        back_populates="knowledge",
        cascade="all, delete-orphan",
        order_by="KnowledgeEvidenceModel.observation_id",
    )
    patterns = relationship(
        "KnowledgePatternModel",
        back_populates="knowledge",
        cascade="all, delete-orphan",
    )
    versions = relationship(
        "KnowledgeVersionModel",
        back_populates="knowledge",
        cascade="all, delete-orphan",
        order_by="KnowledgeVersionModel.knowledge_version",
    )
    transitions = relationship(
        "KnowledgeTransitionModel",
        back_populates="knowledge",
        cascade="all, delete-orphan",
        order_by="KnowledgeTransitionModel.sequence",
    )

    __table_args__ = (
        UniqueConstraint(
            "fingerprint_hash", "knowledge_version", name="uq_fingerprint_version"
        ),
    )


class KnowledgeVersionModel(Base):
    __tablename__ = "knowledge_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_id = Column(
        String(64), ForeignKey("knowledge.knowledge_id"), nullable=False, index=True
    )
    knowledge_version = Column(Integer, nullable=False)
    fingerprint_version = Column(String(32), nullable=False)
    engine_version = Column(String(32), nullable=False)
    schema_version = Column(String(32), nullable=False)
    previous_knowledge_id = Column(String(64), nullable=True)

    knowledge = relationship("KnowledgeModel", back_populates="versions")

    __table_args__ = (
        UniqueConstraint(
            "knowledge_id", "knowledge_version", name="uq_knowledge_version"
        ),
    )


class KnowledgeTransitionModel(Base):
    __tablename__ = "knowledge_transitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_id = Column(
        String(64), ForeignKey("knowledge.knowledge_id"), nullable=False, index=True
    )
    sequence = Column(Integer, nullable=False)
    from_status = Column(String(32), nullable=True)
    to_status = Column(String(32), nullable=False)

    knowledge = relationship("KnowledgeModel", back_populates="transitions")

    __table_args__ = (
        UniqueConstraint("knowledge_id", "sequence", name="uq_transition_sequence"),
    )


class KnowledgeEvidenceModel(Base):
    __tablename__ = "knowledge_evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_id = Column(
        String(64), ForeignKey("knowledge.knowledge_id"), nullable=False, index=True
    )
    observation_id = Column(String(64), nullable=False)
    strength = Column(String(16), nullable=False)
    attributes = Column(JSON, nullable=False, default=dict)

    knowledge = relationship("KnowledgeModel", back_populates="evidence")

    __table_args__ = (
        UniqueConstraint(
            "knowledge_id", "observation_id", name="uq_knowledge_observation"
        ),
    )


class KnowledgePatternModel(Base):
    __tablename__ = "knowledge_patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_id = Column(
        String(64), ForeignKey("knowledge.knowledge_id"), nullable=False, index=True
    )
    pattern_type = Column(String(32), nullable=False)
    description = Column(String(500), nullable=False)
    signature = Column(JSON, nullable=False, default=dict)

    knowledge = relationship("KnowledgeModel", back_populates="patterns")
