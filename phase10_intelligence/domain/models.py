"""
Immutable domain models (frozen dataclasses) for the Intelligence Core.

These models carry no persistence or business logic. Business logic lives
exclusively inside services. Repositories only translate between these
domain models and ORM rows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from .enums import (
    ExperimentStatus,
    GovernanceDecision,
    HypothesisStatus,
    OpportunityStatus,
    RuleStatus,
    StrategyStatus,
)


@dataclass(frozen=True)
class Opportunity:
    id: Optional[int]
    key: str
    source: str
    description: str
    raw_signal: Mapping[str, Any]
    status: OpportunityStatus
    confidence: float
    impact_estimate: float
    novelty_score: float
    fingerprint: str
    version: int = 1


@dataclass(frozen=True)
class OpportunityRanking:
    id: Optional[int]
    opportunity_id: int
    rank_score: float
    components: Mapping[str, float]
    fingerprint: str
    version: int = 1


@dataclass(frozen=True)
class OpportunityValidation:
    id: Optional[int]
    opportunity_id: int
    is_valid: bool
    evidence_count: int
    reasons: Sequence[str]
    fingerprint: str
    version: int = 1


@dataclass(frozen=True)
class Hypothesis:
    id: Optional[int]
    key: str
    statement: str
    origin_opportunity_id: Optional[int]
    status: HypothesisStatus
    confidence: float
    cycles_active: int
    fingerprint: str
    version: int = 1


@dataclass(frozen=True)
class Experiment:
    id: Optional[int]
    key: str
    hypothesis_id: int
    status: ExperimentStatus
    sample_size: int
    effect_size: Optional[float]
    p_value: Optional[float]
    fingerprint: str
    version: int = 1


@dataclass(frozen=True)
class Strategy:
    id: Optional[int]
    key: str
    status: StrategyStatus
    parameters: Mapping[str, Any]
    generation: int
    parent_key: Optional[str]
    fitness_score: float
    fingerprint: str
    version: int = 1


@dataclass(frozen=True)
class StrategyEvaluation:
    id: Optional[int]
    strategy_id: int
    fitness_score: float
    metrics: Mapping[str, float]
    fingerprint: str
    version: int = 1


@dataclass(frozen=True)
class Rule:
    id: Optional[int]
    key: str
    condition_expression: str
    action_expression: str
    status: RuleStatus
    confidence: float
    generation: int
    fingerprint: str
    version: int = 1


@dataclass(frozen=True)
class GovernanceReview:
    id: Optional[int]
    subject_type: str
    subject_key: str
    decision: GovernanceDecision
    risk_score: float
    approvals: int
    rationale: str
    fingerprint: str
    version: int = 1


@dataclass(frozen=True)
class ConfidenceCalibration:
    id: Optional[int]
    subject_type: str
    subject_key: str
    raw_confidence: float
    calibrated_confidence: float
    sample_size: int
    fingerprint: str
    version: int = 1


@dataclass(frozen=True)
class PlanningCycle:
    id: Optional[int]
    cycle_index: int
    horizon: int
    selected_strategy_keys: Sequence[str]
    risk_budget_used: float
    fingerprint: str
    version: int = 1


@dataclass(frozen=True)
class MemoryRecord:
    id: Optional[int]
    subject_type: str
    subject_key: str
    payload: Mapping[str, Any]
    relevance_score: float
    fingerprint: str
    version: int = 1


@dataclass(frozen=True)
class FeedbackRecord:
    id: Optional[int]
    subject_type: str
    subject_key: str
    outcome_score: float
    applied_learning_rate: float
    fingerprint: str
    version: int = 1


@dataclass(frozen=True)
class ReplayRecord:
    id: Optional[int]
    subject_type: str
    subject_key: str
    input_fingerprint: str
    output_fingerprint: str
    engine_name: str
    engine_version: str
    version: int = 1


@dataclass(frozen=True)
class AuditEntry:
    id: Optional[int]
    event_type: str
    subject_type: str
    subject_key: str
    fingerprint: str
    payload: Mapping[str, Any]
    version: int = 1
