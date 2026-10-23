"""
Enumerations used across the Learning Layer domain.
"""

from enum import Enum


class KnowledgeStatus(str, Enum):
    """Lifecycle status of a Knowledge object."""

    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class PatternType(str, Enum):
    """Type of reusable pattern detected by the Learning Engine."""

    STRUCTURAL = "STRUCTURAL"
    BEHAVIORAL = "BEHAVIORAL"
    TEMPORAL = "TEMPORAL"
    CORRELATIVE = "CORRELATIVE"


class EvidenceStrength(str, Enum):
    """Qualitative strength of a single piece of evidence."""

    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
