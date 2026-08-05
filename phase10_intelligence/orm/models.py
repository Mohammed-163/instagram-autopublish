"""
SQLAlchemy ORM models. These are pure persistence schema definitions.
No business logic is permitted here; only column/table definitions and
relationships. Translation to/from domain models happens in repositories.
"""
from __future__ import annotations

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, JSON, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship

from .base import Base


class OpportunityORM(Base):
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), nullable=False, unique=True, index=True)
    source = Column(String(128), nullable=False)
    description = Column(String(1024), nullable=False)
    raw_signal = Column(JSON, nullable=False)
    status = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=False)
    impact_estimate = Column(Float, nullable=False)
    novelty_score = Column(Float, nullable=False)
    fingerprint = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)

    rankings = relationship("OpportunityRankingORM", back_populates="opportunity")
    validations = relationship("OpportunityValidationORM", back_populates="opportunity")


class OpportunityRankingORM(Base):
    __tablename__ = "opportunity_rankings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False)
    rank_score = Column(Float, nullable=False)
    components = Column(JSON, nullable=False)
    fingerprint = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)

    opportunity = relationship("OpportunityORM", back_populates="rankings")


class OpportunityValidationORM(Base):
    __tablename__ = "opportunity_validations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False)
    is_valid = Column(Boolean, nullable=False)
    evidence_count = Column(Integer, nullable=False)
    reasons = Column(JSON, nullable=False)
    fingerprint = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)

    opportunity = relationship("OpportunityORM", back_populates="validations")


class HypothesisORM(Base):
    __tablename__ = "hypotheses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), nullable=False, unique=True, index=True)
    statement = Column(String(1024), nullable=False)
    origin_opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True)
    status = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=False)
    cycles_active = Column(Integer, nullable=False, default=0)
    fingerprint = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)

    experiments = relationship("ExperimentORM", back_populates="hypothesis")


class ExperimentORM(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), nullable=False, unique=True, index=True)
    hypothesis_id = Column(Integer, ForeignKey("hypotheses.id"), nullable=False)
    status = Column(String(32), nullable=False)
    sample_size = Column(Integer, nullable=False, default=0)
    effect_size = Column(Float, nullable=True)
    p_value = Column(Float, nullable=True)
    fingerprint = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)

    hypothesis = relationship("HypothesisORM", back_populates="experiments")


class StrategyORM(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), nullable=False, unique=True, index=True)
    status = Column(String(32), nullable=False)
    parameters = Column(JSON, nullable=False)
    generation = Column(Integer, nullable=False, default=0)
    parent_key = Column(String(128), nullable=True)
    fitness_score = Column(Float, nullable=False, default=0.0)
    fingerprint = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)

    evaluations = relationship("StrategyEvaluationORM", back_populates="strategy")


class StrategyEvaluationORM(Base):
    __tablename__ = "strategy_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    fitness_score = Column(Float, nullable=False)
    metrics = Column(JSON, nullable=False)
    fingerprint = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)

    strategy = relationship("StrategyORM", back_populates="evaluations")


class RuleORM(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), nullable=False, unique=True, index=True)
    condition_expression = Column(String(1024), nullable=False)
    action_expression = Column(String(1024), nullable=False)
    status = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=False)
    generation = Column(Integer, nullable=False, default=0)
    fingerprint = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)


class GovernanceReviewORM(Base):
    __tablename__ = "governance_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_type = Column(String(64), nullable=False)
    subject_key = Column(String(128), nullable=False)
    decision = Column(String(32), nullable=False)
    risk_score = Column(Float, nullable=False)
    approvals = Column(Integer, nullable=False, default=0)
    rationale = Column(String(1024), nullable=False)
    fingerprint = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)

    __table_args__ = (UniqueConstraint("subject_type", "subject_key", "fingerprint", name="uq_governance_subject_fp"),)


class ConfidenceCalibrationORM(Base):
    __tablename__ = "confidence_calibrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_type = Column(String(64), nullable=False)
    subject_key = Column(String(128), nullable=False)
    raw_confidence = Column(Float, nullable=False)
    calibrated_confidence = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=False)
    fingerprint = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)


class PlanningCycleORM(Base):
    __tablename__ = "planning_cycles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle_index = Column(Integer, nullable=False, unique=True)
    horizon = Column(Integer, nullable=False)
    selected_strategy_keys = Column(JSON, nullable=False)
    risk_budget_used = Column(Float, nullable=False)
    fingerprint = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)


class MemoryRecordORM(Base):
    __tablename__ = "memory_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_type = Column(String(64), nullable=False)
    subject_key = Column(String(128), nullable=False)
    payload = Column(JSON, nullable=False)
    relevance_score = Column(Float, nullable=False)
    fingerprint = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)

    __table_args__ = (UniqueConstraint("subject_type", "subject_key", "fingerprint", name="uq_memory_subject_fp"),)


class FeedbackRecordORM(Base):
    __tablename__ = "feedback_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_type = Column(String(64), nullable=False)
    subject_key = Column(String(128), nullable=False)
    outcome_score = Column(Float, nullable=False)
    applied_learning_rate = Column(Float, nullable=False)
    fingerprint = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)


class ReplayRecordORM(Base):
    __tablename__ = "replay_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_type = Column(String(64), nullable=False)
    subject_key = Column(String(128), nullable=False)
    input_fingerprint = Column(String(64), nullable=False)
    output_fingerprint = Column(String(64), nullable=False)
    engine_name = Column(String(128), nullable=False)
    engine_version = Column(String(32), nullable=False)
    version = Column(Integer, nullable=False, default=1)


class AuditEntryORM(Base):
    __tablename__ = "audit_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(128), nullable=False)
    subject_type = Column(String(64), nullable=False)
    subject_key = Column(String(128), nullable=False)
    fingerprint = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=1)
