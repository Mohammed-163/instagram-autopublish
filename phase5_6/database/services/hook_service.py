from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from database.models import HookPattern, HookStatistic
from core.container import container

logger = logging.getLogger(__name__)


class HookService:
    """Service-layer facade over hook_patterns / hook_statistics. Engines
    depend on this — never on the repositories directly."""

    def __init__(self, hook_patterns_repository=None, hook_statistics_repository=None) -> None:
        self.hook_patterns_repository = hook_patterns_repository or container.resolve("hook_patterns_repository")
        self.hook_statistics_repository = hook_statistics_repository or container.resolve("hook_statistics_repository")

    # ------------------------------------------------------------------ hook patterns
    def record_hook_pattern(
        self,
        post_id: Any,
        hook_text: str,
        hook_type: str,
        features: Dict[str, Any],
        category: Optional[str] = None,
    ) -> HookPattern:
        return self.hook_patterns_repository.create(
            post_id=post_id,
            hook_text=hook_text,
            hook_type=hook_type,
            features=features,
            category=category,
        )

    def list_patterns_for_category(self, category: str, limit: int = 200) -> List[HookPattern]:
        return self.hook_patterns_repository.list_for_category(category, limit=limit)

    # ------------------------------------------------------------------ hook statistics ("Hook Rules")
    def record_observation(
        self,
        category: str,
        hook_type: str,
        success_score: float,
        min_sample_size: int,
        high_threshold: float,
        medium_threshold: float,
        rule_confidence_threshold: float,
    ) -> HookStatistic:
        """
        Update the rolling statistic for (category, hook_type) with a new
        observed success_score, recompute success_level/confidence purely
        from the accumulated sample (no hard-coded rule is ever written —
        it is derived fresh from the data every time).
        """
        existing = self.hook_statistics_repository.get_by_category_hook_type(category, hook_type)

        if existing is None:
            sample_size = 1
            success_sum = Decimal(str(success_score))
        else:
            sample_size = existing.sample_size + 1
            success_sum = existing.success_sum + Decimal(str(success_score))

        avg_success = success_sum / sample_size

        if avg_success >= Decimal(str(high_threshold)):
            success_level = "high"
        elif avg_success >= Decimal(str(medium_threshold)):
            success_level = "medium"
        else:
            success_level = "low"

        # Confidence grows with sample size and plateaus — purely statistical.
        confidence = Decimal(str(min(0.99, 1 - (1 / (1 + sample_size)))))
        is_rule = sample_size >= min_sample_size and confidence >= Decimal(str(rule_confidence_threshold))

        if existing is None:
            stat = self.hook_statistics_repository.create(
                category=category,
                hook_type=hook_type,
                sample_size=sample_size,
                success_sum=success_sum,
                avg_success_score=avg_success,
                success_level=success_level,
                confidence=confidence,
                is_rule=is_rule,
            )
        else:
            stat = self.hook_statistics_repository.update(
                existing.id,
                sample_size=sample_size,
                success_sum=success_sum,
                avg_success_score=avg_success,
                success_level=success_level,
                confidence=confidence,
                is_rule=is_rule,
            )
        return stat

    def get_statistic(self, category: str, hook_type: str) -> Optional[HookStatistic]:
        return self.hook_statistics_repository.get_by_category_hook_type(category, hook_type)

    def get_best_hook_type_for_category(self, category: str) -> Optional[HookStatistic]:
        """Return the highest-confidence proven rule for a category, or
        None if nothing qualifies yet (caller should explore instead)."""
        stats = self.hook_statistics_repository.list_for_category(category)
        rules = [s for s in stats if s.is_rule]
        if not rules:
            return None
        return max(rules, key=lambda s: (s.avg_success_score, s.confidence))

    def list_rules(self) -> List[HookStatistic]:
        return self.hook_statistics_repository.list_rules()


hook_service = HookService()
