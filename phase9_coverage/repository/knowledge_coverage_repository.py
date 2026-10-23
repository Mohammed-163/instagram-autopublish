"""
KnowledgeCoverageRepository.

Responsibilities: CRUD, queries, ORM <-> domain mapping. Nothing else.
No business rules, no fingerprint generation, no event publishing, no
validation beyond what is required to map data faithfully.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from phase9_coverage.database.models import CoverageTransitionORM, KnowledgeCoverageORM
from phase9_coverage.domain.dimensions import CoverageDimension, CoverageDimensionSet, DimensionName
from phase9_coverage.domain.gaps import CoverageGap, CoverageGapSet, GapSeverity, GapType
from phase9_coverage.domain.models import CoverageExplainability, CoverageProfile, KnowledgeCoverage


class KnowledgeCoverageRepository:
    """Persistence gateway for KnowledgeCoverage aggregates."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ---- mapping: domain -> ORM -----------------------------------

    @staticmethod
    def _to_orm(coverage: KnowledgeCoverage) -> KnowledgeCoverageORM:
        dims_payload = [
            {
                "name": d.name.value,
                "score": d.score,
                "signals": dict(d.signals),
                "reason": d.reason,
            }
            for d in coverage.coverage_dimensions.as_sorted_tuple()
        ]
        gaps_payload = [
            {
                "gap_type": g.gap_type.value,
                "severity": g.severity.value,
                "description": g.description,
                "related_dimension": g.related_dimension,
                "details": dict(g.details),
            }
            for g in coverage.detected_gaps.as_sorted_tuple()
        ]
        explainability_payload = {
            "coverage_method": coverage.explainability.coverage_method,
            "coverage_reason": coverage.explainability.coverage_reason,
            "dimensions_evaluated": list(coverage.explainability.dimensions_evaluated),
            "gaps_detected": list(coverage.explainability.gaps_detected),
            "confidence_reason": coverage.explainability.confidence_reason,
            "versions": dict(coverage.explainability.versions),
        }
        return KnowledgeCoverageORM(
            coverage_id=coverage.coverage_id,
            knowledge_id=coverage.knowledge_id,
            coverage_profile_id=coverage.coverage_profile.profile_id,
            coverage_profile_name=coverage.coverage_profile.profile_name,
            coverage_profile_description=coverage.coverage_profile.description,
            coverage_profile_metadata_json=json.dumps(
                dict(coverage.coverage_profile.metadata), sort_keys=True
            ),
            coverage_score=coverage.coverage_score,
            coverage_confidence=coverage.coverage_confidence,
            coverage_dimensions_json=json.dumps(dims_payload, sort_keys=True),
            detected_gaps_json=json.dumps(gaps_payload, sort_keys=True),
            fingerprint=coverage.fingerprint,
            structural_fingerprint=coverage.structural_fingerprint,
            feature_fingerprint=coverage.feature_fingerprint,
            fingerprint_hash=coverage.fingerprint_hash,
            fingerprint_version=coverage.fingerprint_version,
            engine_version=coverage.engine_version,
            schema_version=coverage.schema_version,
            versions_json=json.dumps(dict(coverage.versions), sort_keys=True),
            explainability_json=json.dumps(explainability_payload, sort_keys=True),
            created_at=coverage.created_at,
        )

    # ---- mapping: ORM -> domain -----------------------------------

    @staticmethod
    def _to_domain(row: KnowledgeCoverageORM) -> KnowledgeCoverage:
        dims_raw = json.loads(row.coverage_dimensions_json)
        dimensions = CoverageDimensionSet(
            dimensions=tuple(
                CoverageDimension(
                    name=DimensionName(d["name"]),
                    score=d["score"],
                    signals=d.get("signals", {}),
                    reason=d.get("reason", ""),
                )
                for d in dims_raw
            )
        )

        gaps_raw = json.loads(row.detected_gaps_json)
        gaps = CoverageGapSet(
            gaps=tuple(
                CoverageGap(
                    gap_type=GapType(g["gap_type"]),
                    severity=GapSeverity(g["severity"]),
                    description=g["description"],
                    related_dimension=g["related_dimension"],
                    details=g.get("details", {}),
                )
                for g in gaps_raw
            )
        )

        profile = CoverageProfile(
            profile_id=row.coverage_profile_id,
            profile_name=row.coverage_profile_name,
            description=row.coverage_profile_description,
            metadata=json.loads(row.coverage_profile_metadata_json),
        )

        explainability_raw = json.loads(row.explainability_json)
        explainability = CoverageExplainability(
            coverage_method=explainability_raw["coverage_method"],
            coverage_reason=explainability_raw["coverage_reason"],
            dimensions_evaluated=tuple(explainability_raw["dimensions_evaluated"]),
            gaps_detected=tuple(explainability_raw["gaps_detected"]),
            confidence_reason=explainability_raw["confidence_reason"],
            versions=explainability_raw["versions"],
        )

        created_at = row.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        return KnowledgeCoverage(
            coverage_id=row.coverage_id,
            knowledge_id=row.knowledge_id,
            coverage_profile=profile,
            coverage_score=row.coverage_score,
            coverage_dimensions=dimensions,
            detected_gaps=gaps,
            coverage_confidence=row.coverage_confidence,
            fingerprint=row.fingerprint,
            structural_fingerprint=row.structural_fingerprint,
            feature_fingerprint=row.feature_fingerprint,
            fingerprint_hash=row.fingerprint_hash,
            fingerprint_version=row.fingerprint_version,
            engine_version=row.engine_version,
            schema_version=row.schema_version,
            created_at=created_at,
            versions=json.loads(row.versions_json),
            explainability=explainability,
        )

    # ---- CRUD -------------------------------------------------------

    def add(self, coverage: KnowledgeCoverage) -> None:
        self._session.add(self._to_orm(coverage))

    def get_by_id(self, coverage_id: str) -> Optional[KnowledgeCoverage]:
        row = self._session.get(KnowledgeCoverageORM, coverage_id)
        return self._to_domain(row) if row else None

    def get_by_fingerprint_hash(self, fingerprint_hash: str) -> Optional[KnowledgeCoverage]:
        stmt = select(KnowledgeCoverageORM).where(
            KnowledgeCoverageORM.fingerprint_hash == fingerprint_hash
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return self._to_domain(row) if row else None

    def list_by_knowledge_id(self, knowledge_id: str) -> Sequence[KnowledgeCoverage]:
        stmt = (
            select(KnowledgeCoverageORM)
            .where(KnowledgeCoverageORM.knowledge_id == knowledge_id)
            .order_by(KnowledgeCoverageORM.created_at.desc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(r) for r in rows]

    def get_latest_for_knowledge(self, knowledge_id: str) -> Optional[KnowledgeCoverage]:
        results = self.list_by_knowledge_id(knowledge_id)
        return results[0] if results else None

    def delete(self, coverage_id: str) -> bool:
        row = self._session.get(KnowledgeCoverageORM, coverage_id)
        if row is None:
            return False
        self._session.delete(row)
        return True

    # ---- transitions --------------------------------------------------

    def add_transition(
        self,
        *,
        coverage_id: str,
        previous_coverage_id: Optional[str],
        knowledge_id: str,
        previous_score: Optional[float],
        new_score: float,
        occurred_at: datetime,
    ) -> None:
        self._session.add(
            CoverageTransitionORM(
                coverage_id=coverage_id,
                previous_coverage_id=previous_coverage_id,
                knowledge_id=knowledge_id,
                previous_score=previous_score,
                new_score=new_score,
                created_at=occurred_at,
            )
        )

    def list_transitions(self, knowledge_id: str) -> Sequence[CoverageTransitionORM]:
        stmt = (
            select(CoverageTransitionORM)
            .where(CoverageTransitionORM.knowledge_id == knowledge_id)
            .order_by(CoverageTransitionORM.created_at.asc())
        )
        return self._session.execute(stmt).scalars().all()

    def flush(self) -> None:
        self._session.flush()

    def commit(self) -> None:
        self._session.commit()
