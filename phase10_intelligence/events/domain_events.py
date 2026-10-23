"""
Immutable domain events. Events carry only fingerprints and identifiers,
never mutable/live objects, to keep replay deterministic.

Each concrete event "type" below is a small frozen-dataclass subclass with
a fixed default event_type. To keep dataclass field ordering valid (fields
without defaults cannot follow fields with defaults across an inheritance
chain), the base class itself provides defaults for every field.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class DomainEvent:
    subject_key: str = ""
    fingerprint: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    event_type: str = "domain.event"


@dataclass(frozen=True)
class OpportunityDiscovered(DomainEvent):
    event_type: str = "opportunity.discovered"


@dataclass(frozen=True)
class OpportunityValidated(DomainEvent):
    event_type: str = "opportunity.validated"


@dataclass(frozen=True)
class OpportunityRanked(DomainEvent):
    event_type: str = "opportunity.ranked"


@dataclass(frozen=True)
class HypothesisProposed(DomainEvent):
    event_type: str = "hypothesis.proposed"


@dataclass(frozen=True)
class HypothesisResolved(DomainEvent):
    event_type: str = "hypothesis.resolved"


@dataclass(frozen=True)
class ExperimentCompleted(DomainEvent):
    event_type: str = "experiment.completed"


@dataclass(frozen=True)
class StrategyEvolved(DomainEvent):
    event_type: str = "strategy.evolved"


@dataclass(frozen=True)
class StrategyOptimized(DomainEvent):
    event_type: str = "strategy.optimized"


@dataclass(frozen=True)
class RuleEvolved(DomainEvent):
    event_type: str = "rule.evolved"


@dataclass(frozen=True)
class GovernanceDecided(DomainEvent):
    event_type: str = "governance.decided"


@dataclass(frozen=True)
class ConfidenceCalibrated(DomainEvent):
    event_type: str = "confidence.calibrated"


@dataclass(frozen=True)
class PlanningCycleCompleted(DomainEvent):
    event_type: str = "planning.cycle_completed"


@dataclass(frozen=True)
class FeedbackApplied(DomainEvent):
    event_type: str = "feedback.applied"


@dataclass(frozen=True)
class ReplayVerified(DomainEvent):
    event_type: str = "replay.verified"
