"""
Execution Layer Repositories — Phase 6 Part 1.

Two repositories:
  - ExecutionRepository           : CRUD + status queries for execution_records
  - ExecutionTransitionRepository : append-only transition history

Architecture rule: Service → Repository only.
No Engine accesses these directly.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from database.client import get_session
from database.models.execution import ExecutionRecord, ExecutionTransition
from database.repositories.base_repository import BaseRepository


class ExecutionRepository(BaseRepository[ExecutionRecord]):
    """Reads and writes execution_records rows."""

    model = ExecutionRecord

    # ------------------------------------------------------------------ writes

    def create_execution(
        self,
        *,
        decision_candidate_id: Optional[str],
        execution_type: str,
        objective_profile: str = "",
        fingerprint: Optional[str] = None,
        fingerprint_version: Optional[str] = None,
        metadata_: Optional[dict] = None,
        versions: Optional[dict] = None,
        explainability: Optional[dict] = None,
    ) -> ExecutionRecord:
        """Create a new ExecutionRecord with status 'Pending'."""
        now = datetime.now(timezone.utc)
        return self.create(
            decision_candidate_id=decision_candidate_id,
            status="Pending",
            execution_type=execution_type,
            objective_profile=objective_profile,
            fingerprint=fingerprint,
            fingerprint_version=fingerprint_version,
            metadata_=metadata_ or {},
            versions=versions or {},
            explainability=explainability or {},
            result={},
            failure_reason=None,
            scheduled_at=None,
            started_at=None,
            completed_at=None,
            expired_at=None,
            updated_at=now,
        )

    def update_status(
        self,
        execution_id: uuid.UUID,
        status: str,
        *,
        scheduled_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        expired_at: Optional[datetime] = None,
        result: Optional[dict] = None,
        failure_reason: Optional[str] = None,
    ) -> Optional[ExecutionRecord]:
        fields: dict = {"status": status, "updated_at": datetime.now(timezone.utc)}
        if scheduled_at is not None:
            fields["scheduled_at"] = scheduled_at
        if started_at is not None:
            fields["started_at"] = started_at
        if completed_at is not None:
            fields["completed_at"] = completed_at
        if expired_at is not None:
            fields["expired_at"] = expired_at
        if result is not None:
            fields["result"] = result
        if failure_reason is not None:
            fields["failure_reason"] = failure_reason
        return self.update(execution_id, **fields)

    # ------------------------------------------------------------------ reads

    def get_by_fingerprint(self, fingerprint: str) -> Optional[ExecutionRecord]:
        with get_session() as session:
            stmt = select(ExecutionRecord).where(ExecutionRecord.fingerprint == fingerprint).limit(1)
            return session.scalars(stmt).first()

    def get_by_status(self, status: str) -> List[ExecutionRecord]:
        with get_session() as session:
            stmt = (
                select(ExecutionRecord)
                .where(ExecutionRecord.status == status)
                .order_by(ExecutionRecord.created_at)  # deterministic order
            )
            return list(session.scalars(stmt).all())

    def get_by_decision_candidate(self, decision_candidate_id: str) -> List[ExecutionRecord]:
        with get_session() as session:
            stmt = (
                select(ExecutionRecord)
                .where(ExecutionRecord.decision_candidate_id == decision_candidate_id)
                .order_by(ExecutionRecord.created_at)  # deterministic order
            )
            return list(session.scalars(stmt).all())


class ExecutionTransitionRepository(BaseRepository[ExecutionTransition]):
    """Append-only repository for execution_transitions rows.

    Every append must carry: reason, versions, actor, transitioned_at
    (Explainability invariant — mirrors DecisionTransitionRepository pattern).
    """

    model = ExecutionTransition

    def append(
        self,
        *,
        execution_id: str,
        from_status: Optional[str],
        to_status: str,
        reason: str = "",
        actor: str = "system",
        versions: Optional[Dict[str, Any]] = None,
    ) -> ExecutionTransition:
        return self.create(
            execution_id=execution_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            actor=actor,
            versions=versions or {},
            transitioned_at=datetime.now(timezone.utc),
        )

    def get_history(self, execution_id: str) -> List[ExecutionTransition]:
        """Return all transitions for an execution in chronological order (deterministic)."""
        with get_session() as session:
            stmt = (
                select(ExecutionTransition)
                .where(ExecutionTransition.execution_id == execution_id)
                .order_by(ExecutionTransition.transitioned_at)
            )
            return list(session.scalars(stmt).all())


# ---------------------------------------------------------------------------
# Module-level singletons (consumed by container.py)
# ---------------------------------------------------------------------------
execution_repository = ExecutionRepository()
execution_transition_repository = ExecutionTransitionRepository()
