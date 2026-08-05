"""Enumerations shared across the intelligence-core domain."""
from __future__ import annotations
from enum import Enum


class OpportunityStatus(str, Enum):
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    RANKED = "ranked"
    REJECTED = "rejected"
    PROMOTED = "promoted"


class HypothesisStatus(str, Enum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    EXPIRED = "expired"


class ExperimentStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"
    ANALYZED = "analyzed"


class StrategyStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    RETIRED = "retired"
    ARCHIVED = "archived"


class GovernanceDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"
    ESCALATED = "escalated"


class RuleStatus(str, Enum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
