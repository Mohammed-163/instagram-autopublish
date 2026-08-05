from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from database.models import HookFeatureStatistic, HookFeatureValue, HookStructure
from core.container import container

logger = logging.getLogger(__name__)


class HookStructureService:
    """Service-layer facade over hook_structures / hook_feature_values /
    hook_feature_statistics. Engines depend on this — never on the
    repositories directly."""

    def __init__(
        self,
        hook_structures_repository=None,
        hook_feature_values_repository=None,
        hook_feature_statistics_repository=None,
    ) -> None:
        self.hook_structures_repository = hook_structures_repository or container.resolve(
            "hook_structures_repository"
        )
        self.hook_feature_values_repository = hook_feature_values_repository or container.resolve(
            "hook_feature_values_repository"
        )
        self.hook_feature_statistics_repository = hook_feature_statistics_repository or container.resolve(
            "hook_feature_statistics_repository"
        )

    # ------------------------------------------------------------------ hook structures
    def record_hook_structure(
        self,
        post_id: Any,
        hook_text: str,
        features: Dict[str, Any],
        explainability: Dict[str, Any],
        grammar_sequence: List[str],
        analyzer_versions: Dict[str, str],
        category: Optional[str] = None,
        hook_type: Optional[str] = None,
        structural_fingerprint: str = "",
        feature_fingerprint: str = "",
        fingerprint_hash: str = "",
    ) -> HookStructure:
        return self.hook_structures_repository.create(
            post_id=post_id,
            category=category or "General",
            hook_type=hook_type,
            hook_text=hook_text,
            features=features,
            explainability=explainability,
            grammar_sequence=grammar_sequence,
            analyzer_versions=analyzer_versions,
            structural_fingerprint=structural_fingerprint,
            feature_fingerprint=feature_fingerprint,
            fingerprint_hash=fingerprint_hash,
        )

    def get_structure(self, structure_id: Any) -> Optional[HookStructure]:
        return self.hook_structures_repository.get_by_id(structure_id)

    def list_structures_for_post(self, post_id: Any) -> List[HookStructure]:
        return self.hook_structures_repository.list_for_post(post_id)

    def list_structures_for_category(self, category: str, limit: int = 200) -> List[HookStructure]:
        return self.hook_structures_repository.list_for_category(category, limit=limit)

    # ------------------------------------------------------------------ per-feature explainability rows
    def record_feature_values(
        self,
        hook_structure_id: Any,
        post_id: Any,
        features: Dict[str, Any],
        explainability: Dict[str, Any],
    ) -> List[HookFeatureValue]:
        rows: List[HookFeatureValue] = []
        for feature_name, value in features.items():
            expl = explainability.get(feature_name, {})
            rows.append(
                self.hook_feature_values_repository.create(
                    hook_structure_id=hook_structure_id,
                    post_id=post_id,
                    feature_name=feature_name,
                    feature_value={"value": value},
                    extraction_method=expl.get("extraction_method", "unknown"),
                    source=expl.get("source", "hook_text"),
                    analyzer_version=expl.get("analyzer_version", "0.0.0"),
                )
            )
        return rows

    def list_feature_values_for_structure(self, hook_structure_id: Any) -> List[HookFeatureValue]:
        return self.hook_feature_values_repository.list_for_structure(hook_structure_id)

    # ------------------------------------------------------------------ feature importance foundation
    # NOTE: not wired into the pipeline in this phase — a feature's real
    # contribution to success requires the post's success score, which is
    # only known downstream (ObjectiveEngine). The Opportunity Discovery
    # phase will call this once that data is available; the contract is
    # finalized now so no migration/redesign is needed later.
    def record_feature_observation(
        self,
        category: str,
        hook_type: str,
        feature_name: str,
        contribution_score: float,
        min_sample_size: int = 20,
    ) -> HookFeatureStatistic:
        existing = self.hook_feature_statistics_repository.get_by_category_hook_type_feature(
            category, hook_type, feature_name
        )

        if existing is None:
            sample_size = 1
            contribution_sum = Decimal(str(contribution_score))
        else:
            sample_size = existing.sample_size + 1
            contribution_sum = existing.contribution_sum + Decimal(str(contribution_score))

        avg_contribution = contribution_sum / sample_size
        confidence = Decimal(str(min(0.99, 1 - (1 / (1 + sample_size)))))

        if existing is None:
            return self.hook_feature_statistics_repository.create(
                category=category,
                hook_type=hook_type,
                feature_name=feature_name,
                sample_size=sample_size,
                contribution_sum=contribution_sum,
                avg_contribution=avg_contribution,
                confidence=confidence,
            )
        return self.hook_feature_statistics_repository.update(
            existing.id,
            sample_size=sample_size,
            contribution_sum=contribution_sum,
            avg_contribution=avg_contribution,
            confidence=confidence,
        )

    def get_feature_statistic(
        self, category: str, hook_type: str, feature_name: str
    ) -> Optional[HookFeatureStatistic]:
        return self.hook_feature_statistics_repository.get_by_category_hook_type_feature(
            category, hook_type, feature_name
        )


hook_structure_service = HookStructureService()
