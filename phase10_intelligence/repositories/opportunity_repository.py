"""
OpportunityRepository

Repository responsibility: persistence ONLY. No business rules,
thresholds, or scoring logic may appear here -- that belongs in services.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from ..domain.models import Opportunity, OpportunityRanking, OpportunityValidation
from ..domain.enums import OpportunityStatus
from ..orm.models import OpportunityORM, OpportunityRankingORM, OpportunityValidationORM


class OpportunityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, opportunity: Opportunity) -> Opportunity:
        row = OpportunityORM(
            key=opportunity.key,
            source=opportunity.source,
            description=opportunity.description,
            raw_signal=dict(opportunity.raw_signal),
            status=opportunity.status.value,
            confidence=opportunity.confidence,
            impact_estimate=opportunity.impact_estimate,
            novelty_score=opportunity.novelty_score,
            fingerprint=opportunity.fingerprint,
            version=opportunity.version,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def get_by_key(self, key: str) -> Optional[Opportunity]:
        row = self._session.query(OpportunityORM).filter_by(key=key).one_or_none()
        return self._to_domain(row) if row else None

    def list_by_status(self, status: OpportunityStatus) -> List[Opportunity]:
        rows = self._session.query(OpportunityORM).filter_by(status=status.value).all()
        return [self._to_domain(r) for r in rows]

    def update_status(self, key: str, status: OpportunityStatus) -> None:
        row = self._session.query(OpportunityORM).filter_by(key=key).one()
        row.status = status.value
        self._session.flush()

    def add_ranking(self, ranking: OpportunityRanking) -> OpportunityRanking:
        row = OpportunityRankingORM(
            opportunity_id=ranking.opportunity_id,
            rank_score=ranking.rank_score,
            components=dict(ranking.components),
            fingerprint=ranking.fingerprint,
            version=ranking.version,
        )
        self._session.add(row)
        self._session.flush()
        return OpportunityRanking(
            id=row.id, opportunity_id=row.opportunity_id, rank_score=row.rank_score,
            components=row.components, fingerprint=row.fingerprint, version=row.version,
        )

    def add_validation(self, validation: OpportunityValidation) -> OpportunityValidation:
        row = OpportunityValidationORM(
            opportunity_id=validation.opportunity_id,
            is_valid=validation.is_valid,
            evidence_count=validation.evidence_count,
            reasons=list(validation.reasons),
            fingerprint=validation.fingerprint,
            version=validation.version,
        )
        self._session.add(row)
        self._session.flush()
        return OpportunityValidation(
            id=row.id, opportunity_id=row.opportunity_id, is_valid=row.is_valid,
            evidence_count=row.evidence_count, reasons=row.reasons,
            fingerprint=row.fingerprint, version=row.version,
        )

    @staticmethod
    def _to_domain(row: OpportunityORM) -> Opportunity:
        return Opportunity(
            id=row.id, key=row.key, source=row.source, description=row.description,
            raw_signal=row.raw_signal, status=OpportunityStatus(row.status),
            confidence=row.confidence, impact_estimate=row.impact_estimate,
            novelty_score=row.novelty_score, fingerprint=row.fingerprint, version=row.version,
        )
