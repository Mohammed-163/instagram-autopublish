"""
Duplicate Detection / Idempotency service.

Deterministic fingerprint-based deduplication.
Never uses timestamps or random values.
Always sort_keys=True before hashing.

This module is intentionally thin: the canonical duplicate-detection
logic lives in ObservationService (domain layer).  This module provides
a stand-alone, infrastructure-level pre-check that can be used before
opening a full UnitOfWork (e.g. at a message-broker ingestion boundary).
"""
from __future__ import annotations

import json
import hashlib
from typing import Any, Dict

from sqlalchemy.orm import Session

from observation.infrastructure.orm.models import ObservationORM


class DuplicateDetector:
    """
    Checks whether an observation fingerprint is already stored.
    Uses the same canonical serialisation as ObservationFingerprint.from_payload.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_duplicate(self, fingerprint: str) -> bool:
        """Return True if the fingerprint is already in the store."""
        return (
            self._session.query(ObservationORM.id)
            .filter(ObservationORM.fingerprint == fingerprint)
            .first()
        ) is not None

    # ------------------------------------------------------------------
    # Static helpers (stateless, usable without a DB session)
    # ------------------------------------------------------------------

    @staticmethod
    def compute_fingerprint(payload: Dict[str, Any], version: str) -> str:
        """
        Recompute the deterministic fingerprint for a payload dict.
        Mirrors ObservationFingerprint.from_payload exactly.
        sort_keys=True is mandatory — never remove it.
        """
        canonical = json.dumps(
            {"version": version, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
