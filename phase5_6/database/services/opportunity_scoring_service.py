from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from engines.opportunity_detectors.opportunity_candidate import OpportunityCandidate
from core.container import container

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Valid lifecycle states
# -------------------------------------------------------------------------
OPPORTUNITY_STATUSES = [
    "Detected",
    "Validated",
    "Scheduled",
    "Experimented",
    "Resolved",
    "Archived",
    "Expired",
]

# Allowed transitions — enforced by validate_transition()
ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "Detected":           ["Validated", "Archived", "Expired"],
    "Validated":          ["Scheduled", "Archived", "Expired"],
    "Scheduled":          ["Experimented", "Archived"],
    "Experimented":       ["Resolved", "Archived"],
    "Resolved":           ["Archived"],
    "Archived":           [],
    "Expired":            [],
}


class OpportunityScoringService:
    """The ONLY service allowed to compute an Opportunity Score.

    Detectors fill in raw signals (confidence, impact, novelty, knowledge_gap).
    This service is responsible for turning those signals into a single
    Opportunity Score, applying profile-specific weights read from
    SettingsService (never hardcoded).

    Strategy patterns (Growth / Knowledge / Balanced / Conservative / Exploration)
    each define different weight sets — all loaded from settings at runtime.
    """

    SCORING_VERSION = "1.0.0"

    def __init__(self, settings_service: Any = None) -> None:
        self._settings_service = settings_service or container.resolve("settings_service")

    def _get_weights(self, profile: str = "Balanced") -> Dict[str, float]:
        """Load scoring weights for profile exclusively from SettingsService."""
        all_settings = self._settings_service.get("opportunity_scoring", {})
        if not all_settings:
            raise ValueError("opportunity_scoring settings must be provided by SettingsService")
        profiles = all_settings.get("profiles", {})
        profile_weights = profiles.get(profile)
        if not profile_weights:
            raise ValueError(f"Scoring weights for profile '{profile}' missing in settings.")
        return profile_weights

    def score(
        self,
        candidate: OpportunityCandidate,
        profile: str = "Balanced",
    ) -> OpportunityCandidate:
        """Compute opportunity_score and risk. Returns a new immutable candidate."""
        from dataclasses import replace
        weights = self._get_weights(profile)
        risk = self._compute_risk(candidate)

        raw_score = (
            candidate.impact        * weights["impact_weight"]
            + candidate.confidence  * weights["confidence_weight"]
            + candidate.novelty     * weights["novelty_weight"]
            + candidate.knowledge_gap * weights["knowledge_gap_weight"]
            - risk                  * weights["risk_penalty_weight"]
        )
        # Clamp to [0, 1]
        opportunity_score = round(max(0.0, min(1.0, raw_score)), 4)
        
        return replace(
            candidate,
            opportunity_score=opportunity_score,
            risk=round(risk, 4),
            scoring_version=self.SCORING_VERSION,
        )

    def score_batch(
        self,
        candidates: List[OpportunityCandidate],
        profile: str = "Balanced",
    ) -> List[OpportunityCandidate]:
        """Score all candidates and sort deterministically.

        Sort key: score DESC, then detector_name ASC, then opportunity_type ASC.
        This guarantees same input → same ordered output for Replay.
        """
        scored = [self.score(c, profile) for c in candidates]
        return sorted(
            scored,
            key=lambda c: (-(c.opportunity_score or 0.0), c.detector_name, c.opportunity_type),
        )

    def _compute_risk(self, candidate: OpportunityCandidate) -> float:
        """Risk = f(low confidence, low evidence richness)."""
        evidence_richness = min(1.0, candidate.evidence.sample_size / max(1, 100))
        return round((1.0 - candidate.confidence) * (1.0 - evidence_richness), 4)

    def validate_transition(self, from_status: str, to_status: str) -> bool:
        """Check whether a lifecycle transition is allowed."""
        return to_status in ALLOWED_TRANSITIONS.get(from_status, [])


opportunity_scoring_service = OpportunityScoringService()
