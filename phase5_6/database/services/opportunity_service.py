from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.container import container
from core.events import OpportunityDetected, OpportunityTransitioned
from engines.opportunity_detectors.opportunity_candidate import OpportunityCandidate

logger = logging.getLogger(__name__)


class OpportunityService:
    """Service to persist and manage the lifecycle of Opportunities.
    
    This is the only service that talks to OpportunityRepository and 
    OpportunityTransitionRepository.
    """

    FINGERPRINT_VERSION = "2.0"

    def __init__(
        self,
        opportunity_repository: Any = None,
        opportunity_transition_repository: Any = None,
        opportunity_scoring_service: Any = None,
        event_bus: Any = None,
    ) -> None:
        self.opportunity_repository = opportunity_repository or container.resolve("opportunity_repository")
        self.opportunity_transition_repository = opportunity_transition_repository or container.resolve("opportunity_transition_repository")
        self.opportunity_scoring_service = opportunity_scoring_service or container.resolve("opportunity_scoring_service")
        self.event_bus = event_bus or container.resolve("event_bus")

    def _compute_fingerprints(self, candidate: OpportunityCandidate) -> Dict[str, str]:
        """Compute deterministic fingerprints for deduplication and analysis."""
        structural_data = {
            "detector_name": candidate.detector_name,
            "opportunity_type": candidate.opportunity_type,
            "version": self.FINGERPRINT_VERSION,
        }
        feature_data = {
            "related_entities": sorted(candidate.related_entities),
            "evidence_categories": sorted(candidate.explainability.evidence.categories) if candidate.explainability.evidence else [],
        }
        
        struct_raw = json.dumps(structural_data, sort_keys=True)
        feat_raw = json.dumps(feature_data, sort_keys=True)
        
        structural = hashlib.sha256(struct_raw.encode()).hexdigest()[:16]
        feature = hashlib.sha256(feat_raw.encode()).hexdigest()[:16]
        
        combined = json.dumps({"structural": structural, "feature": feature}, sort_keys=True)
        fingerprint_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]
        
        return {
            "structural_fingerprint": structural,
            "feature_fingerprint": feature,
            "fingerprint_hash": fingerprint_hash,
            "fingerprint": fingerprint_hash, # use hash as primary fingerprint
        }

    def persist_candidate(self, candidate: OpportunityCandidate, scoring_profile: str = "Balanced") -> Any:
        """Score and persist a candidate. Deduplicates by fingerprint."""
        fingerprints = self._compute_fingerprints(candidate)
        fingerprint = fingerprints["fingerprint"]
        existing = self.opportunity_repository.get_by_fingerprint(fingerprint)
        if existing:
            logger.info("Opportunity already exists with fingerprint %s, skipping.", fingerprint)
            return existing

        # Score the candidate using the single source of truth for scoring
        scored = self.opportunity_scoring_service.score(candidate, profile=scoring_profile)
        now = datetime.now(timezone.utc)

        # Persist Opportunity
        opp = self.opportunity_repository.create(
            opportunity_type=scored.opportunity_type,
            detector_name=scored.detector_name,
            detector_version=scored.detector_version,
            knowledge_version=scored.knowledge_version,
            coverage_version=scored.coverage_version,
            scoring_version=scored.scoring_version,
            settings_version=scored.settings_version,
            status="Detected",
            confidence=float(scored.confidence),
            impact=float(scored.impact),
            novelty=float(scored.novelty),
            knowledge_gap=float(scored.knowledge_gap),
            risk=float(scored.risk or 0.0),
            opportunity_score=float(scored.opportunity_score or 0.0),
            expected_gain=float(scored.expected_gain),
            explainability=scored.explainability.to_dict(),
            evidence={
                "sample_size": scored.explainability.evidence.sample_size if scored.explainability.evidence else 0,
                "categories": list(scored.explainability.evidence.categories) if scored.explainability.evidence else [],
                "hook_fingerprints": list(scored.explainability.evidence.hook_fingerprints) if scored.explainability.evidence else [],
                "features": dict(scored.explainability.evidence.features) if scored.explainability.evidence else {},
                "time_period_days": scored.explainability.evidence.time_period_days if scored.explainability.evidence else 30,
                "confidence_sources": list(scored.explainability.evidence.confidence_sources) if scored.explainability.evidence else [],
                "raw_data": dict(scored.explainability.evidence.raw_data) if scored.explainability.evidence else {},
            },
            related_entities=scored.related_entities,
            metadata_=scored.metadata,
            fingerprint=fingerprints["fingerprint"],
            structural_fingerprint=fingerprints["structural_fingerprint"],
            feature_fingerprint=fingerprints["feature_fingerprint"],
            fingerprint_hash=fingerprints["fingerprint_hash"],
            detected_at=now,
            updated_at=now,
        )

        # Record initial transition in the lifecycle log
        self.opportunity_transition_repository.create(
            opportunity_id=str(opp.id),
            from_status=None,
            to_status="Detected",
            reason=f"Discovered by detector: {scored.detector_name}",
            actor="system",
            version=scored.detector_version,
            transitioned_at=now,
        )

        # Emit Domain Event
        self.event_bus.publish(
            OpportunityDetected(
                opportunity_id=opp.id,
                opportunity_type=opp.opportunity_type,
                detector_name=opp.detector_name,
                opportunity_score=float(opp.opportunity_score),
                fingerprint=fingerprint,
            )
        )

        return opp

    def transition(
        self,
        opportunity_id: str,
        to_status: str,
        reason: str = "",
        actor: str = "system",
        version: str = "",
    ) -> Any:
        """Transition an opportunity to a new lifecycle state."""
        opp = self.opportunity_repository.get_by_id(opportunity_id)
        if not opp:
            raise ValueError(f"Opportunity {opportunity_id} not found.")

        if not self.opportunity_scoring_service.validate_transition(opp.status, to_status):
            raise ValueError(f"Invalid transition from '{opp.status}' to '{to_status}'.")

        from_status = opp.status
        now = datetime.now(timezone.utc)
        opp = self.opportunity_repository.update_status(opportunity_id, to_status, updated_at=now)

        self.opportunity_transition_repository.create(
            opportunity_id=str(opportunity_id),
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            actor=actor,
            version=version,
            transitioned_at=now,
        )

        self.event_bus.publish(
            OpportunityTransitioned(
                opportunity_id=opp.id,
                from_status=from_status,
                to_status=to_status,
                reason=reason,
            )
        )

        return opp

    def get_validated(self) -> List[Any]:
        return self.opportunity_repository.get_validated()

    def get_by_status(self, status: str) -> List[Any]:
        return self.opportunity_repository.get_by_status(status)

    def expire_stale_opportunities(self, settings_service: Any) -> int:
        """Find stale opportunities and transition them to Expired."""
        # Must come from SettingsService, no hard-coded 30-day value.
        stale_days = int(settings_service.get("opportunity_expiration_days"))
        stale_opps = self.opportunity_repository.get_stale(stale_days)
        
        count = 0
        for opp in stale_opps:
            try:
                self.transition(
                    opportunity_id=str(opp.id),
                    to_status="Expired",
                    reason=f"Exceeded {stale_days} days stale threshold",
                    actor="system_expiration"
                )
                count += 1
            except Exception as e:
                logger.warning("Failed to expire opportunity %s: %s", opp.id, e)
        return count


opportunity_service = OpportunityService()
