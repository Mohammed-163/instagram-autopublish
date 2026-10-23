from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select

from database.client import get_session
from database.models.opportunity import Opportunity, OpportunityTransition
from database.repositories.base_repository import BaseRepository


class OpportunityRepository(BaseRepository[Opportunity]):
    model = Opportunity

    def get_by_status(self, status: str) -> List[Opportunity]:
        """Return all opportunities with the given status, sorted by score descending."""
        with get_session() as session:
            stmt = (
                select(Opportunity)
                .where(Opportunity.status == status)
                .order_by(Opportunity.opportunity_score.desc())
            )
            return list(session.scalars(stmt).all())

    def get_validated(self) -> List[Opportunity]:
        """Return all Validated opportunities — used by StrategyPlanningEngine."""
        return self.get_by_status("Validated")

    def get_by_fingerprint(self, fingerprint: str) -> Optional[Opportunity]:
        """Return a persisted opportunity by fingerprint for deduplication."""
        with get_session() as session:
            stmt = select(Opportunity).where(Opportunity.fingerprint == fingerprint)
            return session.scalars(stmt).first()

    def get_by_type(self, opportunity_type: str) -> List[Opportunity]:
        with get_session() as session:
            stmt = select(Opportunity).where(Opportunity.opportunity_type == opportunity_type)
            return list(session.scalars(stmt).all())

    def update_status(self, opportunity_id: uuid.UUID, status: str, updated_at: Optional[datetime] = None) -> Optional[Opportunity]:
        """Transition an opportunity to a new status."""
        with get_session() as session:
            opp = session.get(Opportunity, opportunity_id)
            if opp:
                opp.status = status
                opp.updated_at = updated_at or datetime.now(timezone.utc)
                session.flush()
                session.refresh(opp)
            return opp


class OpportunityTransitionRepository(BaseRepository[OpportunityTransition]):
    model = OpportunityTransition

    def get_by_opportunity(self, opportunity_id: uuid.UUID) -> List[OpportunityTransition]:
        """Return full transition history for an opportunity, ordered chronologically."""
        with get_session() as session:
            stmt = (
                select(OpportunityTransition)
                .where(OpportunityTransition.opportunity_id == str(opportunity_id))
                .order_by(OpportunityTransition.transitioned_at.asc())
            )
            return list(session.scalars(stmt).all())


opportunity_repository = OpportunityRepository()
opportunity_transition_repository = OpportunityTransitionRepository()
