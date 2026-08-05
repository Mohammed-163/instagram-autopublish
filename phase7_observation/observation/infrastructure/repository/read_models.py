"""
Read models (query-side DTOs).

These are plain, mutable dataclasses used only for returning data
from the Query/Read Layer.  They are NOT domain objects — they carry
no business logic and make no domain invariants.

The split exists so that write-side (Command) and read-side (Query)
concerns stay separated even within a single process (CQRS-lite).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID


@dataclass
class ObservationReadModel:
    """Flat read model returned by query handlers."""
    id: UUID
    fingerprint: str
    execution_id: str
    workflow_id: str
    node_id: str
    tenant_id: str
    payload: Dict[str, Any]
    status: str
    schema_version: str
    observation_version: str


@dataclass
class ObservationSummary:
    """Lightweight summary — no payload — for list queries."""
    id: UUID
    fingerprint: str
    tenant_id: str
    status: str
    observation_version: str
