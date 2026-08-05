"""
LongTermMemoryService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from typing import Any, Mapping

from ..config.settings import Settings
from ..domain.models import MemoryRecord
from ..fingerprint import compute_fingerprint
from ..repositories.memory_repository import MemoryRepository


class LongTermMemoryService:
    """Stores durable records for later knowledge utilization, bounded by a retention limit."""

    def __init__(self, repository: MemoryRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    def remember(self, subject_type: str, subject_key: str, payload: Mapping[str, Any],
                 relevance_score: float) -> MemoryRecord:
        fp_payload = {
            "subject_type": subject_type, "subject_key": subject_key,
            "payload": dict(payload), "relevance_score": relevance_score,
        }
        fp = compute_fingerprint(fp_payload)

        record = MemoryRecord(
            id=None, subject_type=subject_type, subject_key=subject_key,
            payload=dict(payload), relevance_score=relevance_score, fingerprint=fp,
        )
        stored = self._repository.add(record)
        self._repository.prune_lowest(self._settings.memory_retention_limit)
        return stored
