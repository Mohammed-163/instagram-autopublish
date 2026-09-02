"""Persistence subscriber for Phase 10 OpportunityDiscovered events."""
from __future__ import annotations
import json
import logging
import os
from sqlalchemy import create_engine, text

logger = logging.getLogger("phase10_writer")
_engine = None


def wire(phase10_publisher) -> None:
    from phase10_intelligence.events.domain_events import OpportunityDiscovered

    def on_opportunity(event):
        global _engine
        try:
            if _engine is None:
                database_url = os.environ.get("DATABASE_URL")
                if not database_url:
                    raise RuntimeError("DATABASE_URL is not configured")
                _engine = create_engine(database_url, future=True)
            payload = dict(event.payload or {})
            with _engine.begin() as connection:
                opportunity_id = connection.execute(
                    text("""
                        INSERT INTO opportunity_tracking
                            (subject_key, fingerprint, coverage_score, gap_count, source, payload_json)
                        VALUES (:subject_key, :fingerprint, :coverage_score, :gap_count, :source, :payload_json)
                        RETURNING opportunity_id
                    """),
                    {
                        "subject_key": str(event.subject_key),
                        "fingerprint": str(event.fingerprint),
                        "coverage_score": float(payload.get("coverage_score", 0.0)),
                        "gap_count": int(payload.get("gap_count", 0)),
                        "source": str(payload.get("source", "phase9_coverage")),
                        "payload_json": json.dumps(payload, sort_keys=True),
                    },
                ).scalar_one()
            logger.warning("[EVENT-TRACE] Phase 10 wrote opportunity_tracking row: %s", opportunity_id)
        except Exception:
            logger.exception("Phase 10 failed to write opportunity_tracking for subject_key=%s", getattr(event, "subject_key", ""))
            raise

    phase10_publisher.subscribe("opportunity.discovered", on_opportunity)
    logger.info("Phase 10 opportunity_tracking writer wired.")

