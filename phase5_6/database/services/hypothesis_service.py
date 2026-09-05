"""
HypothesisService
=================
Service layer for hypothesis persistence and retrieval.

Responsibility:
- Create new hypothesis records.
- Retrieve hypotheses by status.
- Update hypothesis status (proposed → running → concluded).

Engines interact with hypotheses exclusively through this service; they never
touch hypotheses_repository directly.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from core.container import container

logger = logging.getLogger(__name__)


class HypothesisService:
    def __init__(self, hypotheses_repository: Any = None) -> None:
        self.hypotheses_repository = hypotheses_repository or container.resolve("hypotheses_repository")

    def create(
        self,
        rule_id: uuid.UUID,
        statement: str,
        rationale: str,
        success_criteria: Optional[Dict[str, Any]] = None,
        failure_criteria: Optional[Dict[str, Any]] = None,
        status: str = "proposed",
    ) -> Any:
        """Persist a new hypothesis and return the created record."""
        hypothesis = self.hypotheses_repository.create(
            rule_id=rule_id,
            statement=statement,
            rationale=rationale,
            status=status,
        )
        logger.debug("[HypothesisService] Created hypothesis for rule %s", rule_id)
        return hypothesis

    def list_by_status(self, status: str) -> List[Any]:
        """Return hypotheses filtered by status."""
        if hasattr(self.hypotheses_repository, "list_by_status"):
            return self.hypotheses_repository.list_by_status(status)
        if hasattr(self.hypotheses_repository, "list_all"):
            all_h = self.hypotheses_repository.list_all()
            return [h for h in all_h if getattr(h, "status", None) == status]
        return []

    def get_by_id(self, hypothesis_id: uuid.UUID) -> Optional[Any]:
        """Return a hypothesis by primary key."""
        return self.hypotheses_repository.get_by_id(hypothesis_id)

    def update_status(self, hypothesis_id: uuid.UUID, status: str) -> Optional[Any]:
        """Transition a hypothesis to a new status."""
        if hasattr(self.hypotheses_repository, "update"):
            return self.hypotheses_repository.update(hypothesis_id, status=status)
        logger.warning("[HypothesisService] Repository does not support update — status not persisted")
        return None


hypothesis_service = HypothesisService()
