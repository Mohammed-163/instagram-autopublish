"""
Bridge: Phase9 (Knowledge Coverage) → Phase10 (Intelligence Core).
"""
from __future__ import annotations
import logging

logger = logging.getLogger("bridges.coverage_to_intelligence")


def _build_phase10_event(p9_event: object) -> object:
    from phase10_intelligence.events.domain_events import OpportunityDiscovered
    coverage = getattr(p9_event, "coverage", None)
    knowledge_id = str(getattr(coverage, "knowledge_id", "")) if coverage else ""
    coverage_score = float(getattr(coverage, "coverage_score", 0.0)) if coverage else 0.0
    gaps = getattr(coverage, "detected_gaps", None)
    gap_count = len(gaps) if gaps and hasattr(gaps, "__len__") else 0
    return OpportunityDiscovered(
        subject_key=knowledge_id,
        fingerprint=str(getattr(coverage, "fingerprint", "")) if coverage else "",
        payload={"coverage_score": coverage_score, "gap_count": gap_count,
                 "source": "knowledge_coverage"},
    )


def wire(phase9_publisher: object, phase10_publisher: object) -> None:
    from phase9_coverage.events.events import KnowledgeCoverageCalculated as P9Calculated

    def on_coverage_calculated(event: object) -> None:
        if not isinstance(event, P9Calculated):
            return
        try:
            phase10_publisher.publish(_build_phase10_event(event))
        except Exception:
            logger.exception("coverage_to_intelligence bridge failed for %r", event)

    phase9_publisher.subscribe(on_coverage_calculated)
    logger.info("coverage_to_intelligence bridge wired: Phase9.KnowledgeCoverageCalculated → Phase10")
