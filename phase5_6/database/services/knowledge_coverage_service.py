from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database.models import KnowledgeCoverageSnapshot
from core.container import container
from core.events import KnowledgeCoverageCalculated

logger = logging.getLogger(__name__)


class KnowledgeCoverageService:
    def __init__(
        self,
        knowledge_coverage_repository=None,
        event_bus=None,
    ) -> None:
        self.knowledge_coverage_repository = knowledge_coverage_repository or container.resolve("knowledge_coverage_repository")
        self.event_bus = event_bus or container.resolve("event_bus")

    def create_snapshot(
        self,
        knowledge_version: str,
        coverage_version: str,
        total_entities: int,
        covered_entities: int,
        unknown_entities: int,
        knowledge_coverage: float,
        knowledge_density: float,
        exploration_ratio: float,
        confidence_distribution: Dict[str, Any],
        category_distribution: Dict[str, Any],
        feature_distribution: Dict[str, Any],
        notes: Dict[str, Any],
    ) -> KnowledgeCoverageSnapshot:
        snapshot = self.knowledge_coverage_repository.create(
            calculated_at=datetime.now(timezone.utc),
            knowledge_version=knowledge_version,
            coverage_version=coverage_version,
            total_entities=total_entities,
            covered_entities=covered_entities,
            unknown_entities=unknown_entities,
            knowledge_coverage=knowledge_coverage,
            knowledge_density=knowledge_density,
            exploration_ratio=exploration_ratio,
            confidence_distribution=confidence_distribution,
            category_distribution=category_distribution,
            feature_distribution=feature_distribution,
            notes=notes,
        )

        self.event_bus.publish(
            KnowledgeCoverageCalculated(
                snapshot_id=snapshot.id,
                knowledge_coverage=knowledge_coverage,
                knowledge_density=knowledge_density,
                exploration_ratio=exploration_ratio,
                explainability=notes,
            )
        )

        return snapshot

    def get_latest_snapshot(self) -> Optional[KnowledgeCoverageSnapshot]:
        return self.knowledge_coverage_repository.get_latest()

    def generate_explainability(
        self, current_snapshot: KnowledgeCoverageSnapshot, previous_snapshot: Optional[KnowledgeCoverageSnapshot]
    ) -> Dict[str, Any]:
        """Generate explainability by comparing with the previous snapshot."""
        if not previous_snapshot:
            return {"reason": ["First snapshot created, no historical comparison available."]}
        
        reasons = []
        
        # Coverage changes
        cov_diff = current_snapshot.knowledge_coverage - previous_snapshot.knowledge_coverage
        if cov_diff > 0:
            reasons.append(f"Knowledge coverage increased by {cov_diff:.2f} due to validated rules.")
        elif cov_diff < 0:
            reasons.append(f"Knowledge coverage decreased by {abs(cov_diff):.2f}. This might be due to new entities discovered or old rules deprecated.")
            
        # Density changes
        dens_diff = current_snapshot.knowledge_density - previous_snapshot.knowledge_density
        if dens_diff > 0:
            reasons.append(f"Knowledge density improved (+{dens_diff:.2f}), meaning we have more rules per entity.")
            
        # Entity changes
        new_unknown = current_snapshot.unknown_entities - previous_snapshot.unknown_entities
        if new_unknown > 0:
            reasons.append(f"Identified {new_unknown} new unknown entities.")
            
        return {"reasons": reasons, "changes": {"coverage_diff": float(cov_diff), "density_diff": float(dens_diff)}}

knowledge_coverage_service = KnowledgeCoverageService()
