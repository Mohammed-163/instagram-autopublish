"""
Domain models for the Observation bounded context.
All domain objects are immutable (frozen dataclasses).
No infrastructure concerns live here.
"""
from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------

class ObservationStatus(str, Enum):
    PENDING = "pending"
    RECORDED = "recorded"
    DUPLICATE = "duplicate"
    FAILED = "failed"


@dataclass(frozen=True)
class ObservationFingerprint:
    """
    Deterministic, content-addressable fingerprint.
    Never uses timestamps or random values.
    Always sorts dict keys before hashing.
    """
    value: str

    @classmethod
    def from_payload(cls, payload: Dict[str, Any], version: str) -> "ObservationFingerprint":
        canonical = json.dumps(
            {"version": version, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls(value=digest)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ExecutionContext:
    """Value object capturing what triggered this observation."""
    execution_id: str
    workflow_id: str
    node_id: str
    tenant_id: str
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "node_id": self.node_id,
            "tenant_id": self.tenant_id,
            "extra": dict(sorted(self.extra.items())),
        }


# ---------------------------------------------------------------------------
# Aggregate Root
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Observation:
    """
    Immutable Observation aggregate root.
    Created only via factory methods; never mutated after construction.
    """
    id: UUID
    fingerprint: ObservationFingerprint
    context: ExecutionContext
    payload: Dict[str, Any]
    status: ObservationStatus
    schema_version: str
    observation_version: str

    def is_duplicate(self) -> bool:
        return self.status == ObservationStatus.DUPLICATE

    def mark_duplicate(self) -> "Observation":
        """Return a new Observation with DUPLICATE status (immutable update)."""
        return Observation(
            id=self.id,
            fingerprint=self.fingerprint,
            context=self.context,
            payload=self.payload,
            status=ObservationStatus.DUPLICATE,
            schema_version=self.schema_version,
            observation_version=self.observation_version,
        )

    def mark_recorded(self) -> "Observation":
        return Observation(
            id=self.id,
            fingerprint=self.fingerprint,
            context=self.context,
            payload=self.payload,
            status=ObservationStatus.RECORDED,
            schema_version=self.schema_version,
            observation_version=self.observation_version,
        )
