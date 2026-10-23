"""
Domain Events.

Every event that flows through the EventBus (see core.event_bus) must be one
of the classes defined here — never a raw string. This is what lets future
engines subscribe to typed domain events instead of raw strings.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, List, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DomainEvent:
    """Base class for every domain event."""

    EVENT_TYPE: ClassVar[str] = "domain_event"

    event_id: uuid.UUID = field(default_factory=uuid.uuid4, kw_only=True)
    occurred_at: datetime = field(default_factory=_utcnow, kw_only=True)

    @property
    def event_type(self) -> str:
        return self.EVENT_TYPE

    def payload(self) -> Dict[str, Any]:
        """Everything except the bookkeeping fields, for persistence/logging."""
        skip = {"event_id", "occurred_at"}
        return {f.name: getattr(self, f.name) for f in fields(self) if f.name not in skip}


# ---------------------------------------------------------------------------
# Phase 2 (Part 1) Event Pipeline:
# PostPublished -> ObservationRecorded -> FeaturesExtracted -> FeatureScoresCalculated -> PatternsDiscovered -> KnowledgeUpdated
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PostPublished(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "post_published"

    post_id: uuid.UUID
    instagram_media_id: Optional[str] = None
    topic_id: Optional[uuid.UUID] = None


@dataclass(frozen=True)
class ObservationRecorded(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "observation_recorded"

    post_id: uuid.UUID
    observation_type: str = "post_published"
    payload_data: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeaturesExtracted(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "features_extracted"

    post_id: uuid.UUID
    features: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureScoresCalculated(DomainEvent):
    """Emitted by FeatureScoringEngine right after FeaturesExtracted.
    Pure content-quality scores (readability/visual/hook/density) — computed
    before publish, independent of any real-world performance data."""

    EVENT_TYPE: ClassVar[str] = "feature_scores_calculated"

    post_id: uuid.UUID
    scores: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class PatternsDiscovered(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "patterns_discovered"

    pattern_id: uuid.UUID
    pattern_name: str
    conditions: Dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0
    metrics_summary: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeUpdated(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "knowledge_updated"

    knowledge_version_id: Optional[uuid.UUID] = None
    summary: Optional[str] = None


# ---------------------------------------------------------------------------
# Phase 2 (Part 2) Closed Learning Loop Pipeline:
# KnowledgeUpdated -> ConfidenceUpdated -> HypothesisCreated -> ExperimentCompleted -> DecisionProposed -> DecisionCreated -> WeeklyPlanCreated
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfidenceUpdated(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "confidence_updated"

    rule_id: uuid.UUID
    confidence_score: float
    sample_size: int = 0
    success_count: int = 0
    failure_count: int = 0
    reasoning: str = ""


@dataclass(frozen=True)
class HypothesisCreated(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "hypothesis_created"

    hypothesis_id: uuid.UUID
    rule_id: uuid.UUID
    reason: str
    expected_change: str
    success_criteria: Dict[str, Any] = field(default_factory=dict)
    failure_criteria: Dict[str, Any] = field(default_factory=dict)
    explainability: str = ""


@dataclass(frozen=True)
class ExperimentCompleted(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "experiment_completed"

    experiment_id: uuid.UUID
    hypothesis_id: uuid.UUID
    variant_a_metrics: Dict[str, Any] = field(default_factory=dict)
    variant_b_metrics: Dict[str, Any] = field(default_factory=dict)
    winner: str = "variant_a"
    summary: str = ""
    explainability: str = ""


@dataclass(frozen=True)
class DecisionProposed(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "decision_proposed"

    proposal_id: uuid.UUID
    decision_type: str
    reasoning: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence_level: float = 0.0
    rejected_alternatives: List[Dict[str, Any]] = field(default_factory=list)
    explainability: str = ""


@dataclass(frozen=True)
class DecisionCreated(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "decision_created"

    decision_id: uuid.UUID
    proposal_id: uuid.UUID
    action: str
    status: str = "approved"
    explainability: str = ""


@dataclass(frozen=True)
class WeeklyPlanCreated(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "weekly_plan_created"

    plan_id: uuid.UUID
    status: str = "draft"
    target_posts: int = 10
    content_mix: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Additional Events
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MetricsCollected(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "metrics_collected"

    post_id: uuid.UUID
    period: str
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentFinished(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "experiment_finished"

    experiment_id: uuid.UUID
    hypothesis_id: Optional[uuid.UUID] = None
    outcome: Optional[str] = None


@dataclass(frozen=True)
class RuleActivated(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "rule_activated"

    rule_id: uuid.UUID
    reason: Optional[str] = None


@dataclass(frozen=True)
class RulePerformanceEvaluated(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "rule_performance_evaluated"

    rule_id: uuid.UUID
    confidence_score: float
    reason: Optional[str] = None

@dataclass(frozen=True)
class MetricCollected(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "metric_collected"
    post_id: uuid.UUID
    metric_name: str
    raw_value: float
    measured_at: datetime
    interval_type: str
    source: str
    source_version: str
    collector_version: str
    confidence: float

@dataclass(frozen=True)
class QualityValidated(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "quality_validated"
    post_id: uuid.UUID
    metric_name: str
    raw_value: float
    measured_at: datetime
    interval_type: str
    source: str
    source_version: str
    collector_version: str
    confidence: float

@dataclass(frozen=True)
class MetricNormalized(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "metric_normalized"
    post_id: uuid.UUID
    metric_name: str
    raw_value: float
    normalized_value: float
    measured_at: datetime
    interval_type: str
    source: str
    source_version: str
    collector_version: str
    normalization_version: str
    confidence: float

@dataclass(frozen=True)
class ReasoningRecorded(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "reasoning_recorded"
    post_id: uuid.UUID
    node_type: str
    context: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[uuid.UUID] = None



@dataclass(frozen=True)
class SuccessScoreCalculated(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "success_score_calculated"
    post_id: uuid.UUID
    score: float
    explainability: Dict[str, Any]
    objective_version: str
    objective_profile: str
    weight_config_version: str
    settings_version: str


@dataclass(frozen=True)
class PerformanceEvaluated(DomainEvent):
    """Emitted by PerformanceEvaluationEngine after SuccessScoreCalculated.
    Compares the pre-publish quality prediction (FeatureScoresCalculated)
    against the actual real-world success score, so the system can learn
    where its content-quality judgment was right or wrong."""

    EVENT_TYPE: ClassVar[str] = "performance_evaluated"

    post_id: uuid.UUID
    success_score: float
    predicted_quality_score: float
    performance_gap: float  # success_score - predicted_quality_score
    explainability: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class HookAnalyzed(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "hook_analyzed"

    post_id: uuid.UUID
    hook_text: str = ""
    hook_type: str = "curiosity"
    category: Optional[str] = None
    features: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HookRuleCreated(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "hook_rule_created"

    statistic_id: uuid.UUID
    category: str = ""
    hook_type: str = ""
    success_level: str = "low"
    confidence: float = 0.0
    sample_size: int = 0


@dataclass(frozen=True)
class StrategyGenerated(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "strategy_generated"

    candidate_id: uuid.UUID
    strategy_version_id: uuid.UUID
    category: str = ""
    topic: str = ""
    hook_type: str = ""
    objective: str = ""
    reason: str = ""
    confidence: float = 0.0
    expected_success: float = 0.0
    is_experiment: bool = False


@dataclass(frozen=True)
class WeeklyStrategyCompleted(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "weekly_strategy_completed"

    strategy_version_id: uuid.UUID
    version_number: int = 0
    total_candidates: int = 0
    status: str = "planned"


@dataclass(frozen=True)
class HookFeatureExtracted(DomainEvent):
    """Emitted right after the Hook Feature Analyzer plugins have run on a
    hook's text, before anything is persisted."""

    EVENT_TYPE: ClassVar[str] = "hook_feature_extracted"

    post_id: uuid.UUID
    hook_text: str = ""
    features: Dict[str, Any] = field(default_factory=dict)
    explainability: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HookFeaturesStored(DomainEvent):
    """Emitted once the extracted features have been persisted as
    HookFeatureValue rows."""

    EVENT_TYPE: ClassVar[str] = "hook_features_stored"

    structure_id: uuid.UUID
    post_id: uuid.UUID
    feature_count: int = 0


@dataclass(frozen=True)
class HookStructureLearned(DomainEvent):
    """Terminal event of HookStructureLearningEngine: the hook's full
    structure (features + grammar_sequence) has been learned and
    persisted."""

    EVENT_TYPE: ClassVar[str] = "hook_structure_learned"

    structure_id: uuid.UUID
    post_id: uuid.UUID
    category: str = "General"
    hook_type: Optional[str] = None
    grammar_sequence: List[str] = field(default_factory=list)
    feature_count: int = 0
    structural_fingerprint: str = ""
    feature_fingerprint: str = ""
    fingerprint_hash: str = ""


@dataclass(frozen=True)
class KnowledgeCoverageCalculated(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "knowledge_coverage_calculated"
    snapshot_id: uuid.UUID
    knowledge_coverage: float
    knowledge_density: float
    exploration_ratio: float
    explainability: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class KnowledgeCoverageUpdated(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "knowledge_coverage_updated"
    snapshot_id: uuid.UUID
    changes: Dict[str, Any] = field(default_factory=dict)
    
@dataclass(frozen=True)
class ObjectiveProfileChanged(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "objective_profile_changed"
    profile_name: str
    weights: Dict[str, Any]
    version: str


# ---------------------------------------------------------------------------
# Phase C — Opportunity Intelligence Layer Events
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OpportunityDetected(DomainEvent):
    """Emitted when a new opportunity is discovered and persisted."""
    EVENT_TYPE: ClassVar[str] = "opportunity_detected"
    opportunity_id: uuid.UUID
    opportunity_type: str
    detector_name: str
    opportunity_score: float = 0.0
    fingerprint: str = ""


@dataclass(frozen=True)
class OpportunityTransitioned(DomainEvent):
    """Emitted when an opportunity moves to a new lifecycle status."""
    EVENT_TYPE: ClassVar[str] = "opportunity_transitioned"
    opportunity_id: uuid.UUID
    from_status: Optional[str]
    to_status: str
    reason: str = ""


@dataclass(frozen=True)
class DecisionCandidateProposed(DomainEvent):
    """Phase 5 (Part 1) — Decision Layer Foundation.

    Named `DecisionCandidateProposed` (not `DecisionProposed`) to avoid
    colliding with the pre-existing `DecisionProposed` event already used by
    the Phase 2 `DecisionEngine` (experiment -> decision flow). Same intent
    ("propose"), different pipeline.
    """

    EVENT_TYPE: ClassVar[str] = "decision_candidate_proposed"

    decision_candidate_id: uuid.UUID
    strategy_version_id: Optional[uuid.UUID] = None
    decision_type: str = ""
    objective_profile: str = ""
    decision_score: float = 0.0
    fingerprint: str = ""


@dataclass(frozen=True)
class DecisionCandidateApproved(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "decision_candidate_approved"

    decision_candidate_id: uuid.UUID
    reason: str = ""
    actor: str = "system"


@dataclass(frozen=True)
class DecisionCandidateRejected(DomainEvent):
    EVENT_TYPE: ClassVar[str] = "decision_candidate_rejected"

    decision_candidate_id: uuid.UUID
    reason: str = ""
    actor: str = "system"


@dataclass(frozen=True)
class OpportunitiesDiscovered(DomainEvent):
    """Emitted by OpportunityDiscoveryEngine after a full detection run."""
    EVENT_TYPE: ClassVar[str] = "opportunities_discovered"
    coverage_snapshot_id: Optional[uuid.UUID]
    total_detected: int = 0
    opportunity_types: List[str] = field(default_factory=list)
    top_score: float = 0.0


# ---------------------------------------------------------------------------
# Phase 6 (Part 1) — Execution Layer Foundation Events
#
# Pipeline (foundation only — no real execution):
#   DecisionCandidateApproved → ExecutionPending
#
# Full lifecycle events (emitted by Phase6ExecutionService on each transition):
#   ExecutionPending   : Execution created, status set to Pending
#   ExecutionScheduled : Pending → Scheduled
#   ExecutionStarted   : Scheduled → Running
#   ExecutionCompleted : Running → Completed
#   ExecutionFailed    : Running → Failed
#   ExecutionCancelled : Pending|Scheduled → Cancelled
#   ExecutionExpired   : Pending|Scheduled → Expired
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExecutionPending(DomainEvent):
    """Emitted by Phase6ExecutionEngine when an ExecutionRecord is created
    with status Pending (reacting to DecisionCandidateApproved)."""
    EVENT_TYPE: ClassVar[str] = "execution_pending"

    execution_id: uuid.UUID
    decision_candidate_id: Optional[str] = None
    execution_type: str = ""
    objective_profile: str = ""
    fingerprint: str = ""


@dataclass(frozen=True)
class ExecutionScheduled(DomainEvent):
    """Emitted when an execution transitions Pending → Scheduled."""
    EVENT_TYPE: ClassVar[str] = "execution_scheduled"

    execution_id: uuid.UUID
    decision_candidate_id: Optional[str] = None
    execution_type: str = ""


@dataclass(frozen=True)
class ExecutionStarted(DomainEvent):
    """Emitted when an execution transitions Scheduled → Running."""
    EVENT_TYPE: ClassVar[str] = "execution_started"

    execution_id: uuid.UUID
    decision_candidate_id: Optional[str] = None
    execution_type: str = ""


@dataclass(frozen=True)
class ExecutionCompleted(DomainEvent):
    """Emitted when an execution transitions Running → Completed."""
    EVENT_TYPE: ClassVar[str] = "execution_completed"

    execution_id: uuid.UUID
    decision_candidate_id: Optional[str] = None
    execution_type: str = ""
    result: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionFailed(DomainEvent):
    """Emitted when an execution transitions Running → Failed."""
    EVENT_TYPE: ClassVar[str] = "execution_failed"

    execution_id: uuid.UUID
    decision_candidate_id: Optional[str] = None
    execution_type: str = ""
    failure_reason: str = ""


@dataclass(frozen=True)
class ExecutionCancelled(DomainEvent):
    """Emitted when an execution transitions Pending|Scheduled → Cancelled."""
    EVENT_TYPE: ClassVar[str] = "execution_cancelled"

    execution_id: uuid.UUID
    decision_candidate_id: Optional[str] = None
    execution_type: str = ""
    reason: str = ""


@dataclass(frozen=True)
class ExecutionExpired(DomainEvent):
    """Emitted when an execution transitions Pending|Scheduled → Expired."""
    EVENT_TYPE: ClassVar[str] = "execution_expired"

    execution_id: uuid.UUID
    decision_candidate_id: Optional[str] = None
    execution_type: str = ""
    reason: str = ""


# ---------------------------------------------------------------------------
# Phase 5 (Part 2) — Decision Lifecycle Completion events
# (present in Phase5 core/events.py; missing from Phase6 merge — added here)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DecisionScheduled(DomainEvent):
    """Phase 5 (Part 2) — Decision Lifecycle Completion. Approved -> Scheduled."""
    EVENT_TYPE: ClassVar[str] = "decision_scheduled"
    decision_candidate_id: uuid.UUID
    reason: str = ""
    actor: str = "system"


@dataclass(frozen=True)
class DecisionExecuted(DomainEvent):
    """Phase 5 (Part 2) — Decision Lifecycle Completion. Scheduled -> Executed."""
    EVENT_TYPE: ClassVar[str] = "decision_executed"
    decision_candidate_id: uuid.UUID
    reason: str = ""
    actor: str = "system"


@dataclass(frozen=True)
class DecisionCancelled(DomainEvent):
    """Phase 5 (Part 2) — Decision Lifecycle Completion. Approved/Scheduled -> Cancelled."""
    EVENT_TYPE: ClassVar[str] = "decision_cancelled"
    decision_candidate_id: uuid.UUID
    reason: str = ""
    actor: str = "system"


@dataclass(frozen=True)
class DecisionExpired(DomainEvent):
    """Phase 5 (Part 2) — Decision Lifecycle Completion. Scheduled -> Expired."""
    EVENT_TYPE: ClassVar[str] = "decision_expired"
    decision_candidate_id: uuid.UUID
    reason: str = ""
    actor: str = "system"
