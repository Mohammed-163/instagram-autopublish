from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Dict, List

from core.container import container
from engines.decision.decision_candidate import DecisionCandidate

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Valid lifecycle states for a DecisionCandidate
#
# Proposed -> Approved -> Scheduled -> Executed          (happy path)
#          -> Rejected                                    (terminal)
#                          Scheduled -> Cancelled          (terminal)
#                          Scheduled -> Expired            (terminal)
#          Approved -> Cancelled                           (terminal)
# -------------------------------------------------------------------------
DECISION_STATUSES = [
    "Proposed", "Approved", "Rejected",
    "Scheduled", "Executed", "Cancelled", "Expired",
]

# Allowed transitions — enforced by validate_transition()
ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "Proposed": ["Approved", "Rejected"],
    "Approved": ["Scheduled", "Cancelled"],
    "Rejected": [],
    "Scheduled": ["Executed", "Cancelled", "Expired"],
    "Executed": [],
    "Cancelled": [],
    "Expired": [],
}


class DecisionScoringService:
    """The ONLY service allowed to compute a Decision Score.

    Reads ALL weights from SettingsService — no hardcoded business values.
    Supports five scoring profiles: Balanced, Growth, Knowledge, Exploration,
    Conservative. Each profile defines its own weight set, loaded from
    settings at runtime (never hardcoded in code).
    """

    SCORING_VERSION = "1.0.0"
    SUPPORTED_PROFILES = ("Balanced", "Growth", "Knowledge", "Exploration", "Conservative")

    def __init__(self, settings_service: Any = None) -> None:
        # Resolved lazily (see _settings_service property) rather than eagerly
        # here, because this singleton is constructed during container
        # bring-up, before "settings_service" is necessarily registered yet.
        self._settings_service_override = settings_service
        self._settings_service_cache: Any = None

    @property
    def _settings_service(self) -> Any:
        if self._settings_service_override is not None:
            return self._settings_service_override
        if self._settings_service_cache is None:
            self._settings_service_cache = container.resolve("settings_service")
        return self._settings_service_cache

    def _get_weights(self, profile: str = "Balanced") -> Dict[str, float]:
        """Load scoring weights for a profile exclusively from SettingsService."""
        all_settings = self._settings_service.get("decision_scoring", {})
        if not all_settings:
            raise ValueError("decision_scoring settings must be provided by SettingsService")
        profiles = all_settings.get("profiles", {})
        profile_weights = profiles.get(profile)
        if not profile_weights:
            raise ValueError(f"Decision scoring weights for profile '{profile}' missing in settings.")
        return profile_weights

    def score(self, candidate: DecisionCandidate, profile: str = "Balanced") -> DecisionCandidate:
        """Compute decision_score and risk. Returns a new immutable candidate."""
        weights = self._get_weights(profile)
        risk = self._compute_risk(candidate)

        raw_score = (
            candidate.confidence * weights["confidence_weight"]
            + candidate.expected_gain * weights["gain_weight"]
            - risk * weights["risk_penalty_weight"]
        )
        # Clamp to [0, 1]
        decision_score = round(max(0.0, min(1.0, raw_score)), 4)

        return replace(
            candidate,
            decision_score=decision_score,
            risk=round(risk, 4),
            scoring_version=self.SCORING_VERSION,
        )

    def score_batch(
        self,
        candidates: List[DecisionCandidate],
        profile: str = "Balanced",
    ) -> List[DecisionCandidate]:
        """Score all candidates and sort deterministically.

        Sort key: score DESC, then decision_type ASC. Guarantees same input
        -> same ordered output for replay.
        """
        scored = [self.score(c, profile) for c in candidates]
        return sorted(
            scored,
            key=lambda c: (-(c.decision_score or 0.0), c.decision_type),
        )

    def _compute_risk(self, candidate: DecisionCandidate) -> float:
        """Risk = f(low confidence, low evidence richness from related opportunities)."""
        richness = min(1.0, len(candidate.related_opportunities) / max(1, 3))
        base_risk = candidate.risk if candidate.risk else (1.0 - candidate.confidence)
        return round(max(0.0, min(1.0, base_risk * (1.0 - richness))), 4)

    def validate_transition(self, from_status: str, to_status: str) -> bool:
        """Check whether a lifecycle transition is allowed."""
        return to_status in ALLOWED_TRANSITIONS.get(from_status, [])


decision_scoring_service = DecisionScoringService()
