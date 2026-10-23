"""
Bridge: Phase8 (Learning) → Phase9 (Knowledge Coverage).

Subscribes to Phase8's KnowledgeValidated events and routes them
to Phase9's run function.
"""
from __future__ import annotations
import logging
from typing import Callable, Optional

logger = logging.getLogger("bridges.learning_to_coverage")


def _build_phase9_event(p8_validated_event: object,
                        knowledge_lookup: Optional[Callable] = None) -> object:
    from phase9_coverage.domain.inbound_events import KnowledgeValidated as P9KnowledgeValidated

    knowledge_id = str(getattr(p8_validated_event, "knowledge_id", ""))
    fingerprint_hash = str(getattr(p8_validated_event, "fingerprint_hash", ""))

    topics: tuple = ()
    categories: tuple = ()
    evidence_count: int = 0
    confidence_scores: tuple = ()
    freshness_timestamps: tuple = ()
    relationships: tuple = ()
    statistics: dict = {"fingerprint_hash": fingerprint_hash}

    if knowledge_lookup is not None:
        try:
            knowledge = knowledge_lookup(knowledge_id)
            if knowledge is not None:
                evidence = getattr(knowledge, "evidence", ())
                evidence_count = len(evidence)
                confidence = getattr(knowledge, "confidence", None)
                if confidence is not None:
                    confidence_scores = (float(getattr(confidence, "score", 0.0)),)
                pattern = getattr(knowledge, "pattern", None)
                if pattern is not None:
                    sig = dict(getattr(pattern, "signature", {}))
                    topics = tuple(sig.get("topics", "").split(",")) if "topics" in sig else ()
                version = getattr(knowledge, "version", None)
                if version is not None:
                    freshness_timestamps = (str(getattr(version, "knowledge_version", 1)),)
        except Exception:
            logger.warning("learning_to_coverage: enrichment failed for %s", knowledge_id, exc_info=True)

    return P9KnowledgeValidated(
        knowledge_id=knowledge_id,
        knowledge_versions=(fingerprint_hash,) if fingerprint_hash else (),
        topics=topics,
        categories=categories,
        evidence_count=evidence_count,
        confidence_scores=confidence_scores,
        freshness_timestamps=freshness_timestamps,
        relationships=relationships,
        statistics=statistics,
    )


def wire(phase8_publisher: object,
         phase9_run: Callable[[object], object],
         phase8_knowledge_lookup: Optional[Callable] = None) -> None:
    from phase8_learning.events.events import KnowledgeValidated as P8KnowledgeValidated

    def on_knowledge_validated(event: object) -> None:
        if not isinstance(event, P8KnowledgeValidated):
            return
        try:
            p9_event = _build_phase9_event(event, phase8_knowledge_lookup)
            phase9_run(p9_event)
        except Exception:
            logger.exception("learning_to_coverage bridge failed for %r", event)

    phase8_publisher.subscribe(P8KnowledgeValidated, on_knowledge_validated)
    logger.info("learning_to_coverage bridge wired: Phase8.KnowledgeValidated → Phase9")
