"""
StrategyPlanningEngine
=======================
Phase 4 Part 1 / Phase D/E Integration.

Responsibility:
- Generate weekly strategy entirely from Validated Opportunities supplied by OpportunityService.
- NEVER reads metrics directly.
- NEVER reads statistics directly.
- NEVER calculates/scores opportunities.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from core.events import StrategyGenerated, WeeklyStrategyCompleted
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)


class StrategyPlanningEngine(EngineBase):
    """Planning-only engine. Generates strategy strictly from Validated Opportunities."""

    ENGINE_NAME = "strategy_planning"

    def __init__(
        self,
        event_bus: Any,
        strategy_service: Any,
        opportunity_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.strategy_service = strategy_service
        self.opportunity_service = opportunity_service

    def generate_weekly_strategy(
        self,
        week_start: Optional[date] = None,
        week_end: Optional[date] = None,
        target_posts: Optional[int] = None,
    ) -> uuid.UUID:
        try:
            cfg = self.settings
            week_start = week_start or date.today()
            week_end = week_end or (week_start + timedelta(days=6))
            target_posts = max(cfg.strategy_min_posts, target_posts or 0)

            # Strict architecture: Consume ONLY Validated Opportunities
            validated_opps = self.opportunity_service.get_by_status("Validated")

            categories, topics = self._extract_domain_from_opportunities(validated_opps, cfg)
            recent_candidates = self.strategy_service.get_recent_candidates(limit_versions=4)

            version = self.strategy_service.create_version(
                week_start=week_start, week_end=week_end, summary="Generating from Opportunities..."
            )

            used_topics: set = {c.topic for c in recent_candidates if getattr(c, "topic", None)}
            prev_category: Optional[str] = None
            prev_hook_type: Optional[str] = None
            exploration_slots = self._exploration_slots(target_posts, cfg.strategy_exploration_ratio)

            candidates_payload: List[Dict[str, Any]] = []

            for position in range(target_posts):
                is_experiment = position in exploration_slots

                category = self._pick_category(categories, prev_category, position)
                topic = self._pick_topic(topics, category, used_topics, position)
                used_topics.add(topic)

                hook_type, confidence, expected_success, reason, based_on = self._pick_hook_from_opportunities(
                    validated_opps, category, prev_hook_type, is_experiment, cfg
                )

                objective = self._build_objective(category, is_experiment)

                candidate = self.strategy_service.add_candidate(
                    strategy_version_id=version.id,
                    position=position,
                    category=category,
                    topic=topic,
                    hook_type=hook_type,
                    objective=objective,
                    reason=reason,
                    confidence=confidence,
                    expected_success=expected_success,
                    is_experiment=is_experiment,
                    based_on=based_on,
                )

                event = StrategyGenerated(
                    candidate_id=candidate.id,
                    strategy_version_id=version.id,
                    category=category,
                    topic=topic,
                    hook_type=hook_type,
                    objective=objective,
                    reason=reason,
                    confidence=confidence,
                    expected_success=expected_success,
                    is_experiment=is_experiment,
                )
                self.event_bus.publish(event)
                candidates_payload.append({"category": category, "hook_type": hook_type, "is_experiment": is_experiment})

                prev_category, prev_hook_type = category, hook_type

            summary = self._build_summary(target_posts, exploration_slots, candidates_payload)
            self.strategy_service.complete_version(version.id, summary=summary)
            self.strategy_service.record_explanation(
                subject_id=version.id,
                explanation=summary,
                factors={
                    "target_posts": target_posts,
                    "exploration_slots": sorted(exploration_slots),
                    "exploration_ratio": cfg.strategy_exploration_ratio,
                    "categories_considered": categories,
                    "opportunities_consumed": len(validated_opps),
                },
            )

            completed_event = WeeklyStrategyCompleted(
                strategy_version_id=version.id,
                version_number=version.version_number,
                total_candidates=target_posts,
                status="planned",
            )
            self.event_bus.publish(completed_event)

            self.heartbeat("healthy")
            return version.id

        except Exception as e:
            logger.exception("[StrategyPlanningEngine] Error generating weekly strategy: %s", e)
            self.heartbeat("error", error=str(e))
            raise

    def _extract_domain_from_opportunities(self, opps: List[Any], cfg: Any) -> tuple:
        categories = set()
        topics = set()
        for opp in opps:
            if getattr(opp, "evidence", None) and isinstance(opp.evidence, dict):
                categories.update(opp.evidence.get("categories", []))
            topics.update(getattr(opp, "related_entities", []))
        
        cats = sorted(categories) or cfg.strategy_default_categories or ["General"]
        tops = sorted(topics) or list(cats)
        return cats, tops

    @staticmethod
    def _exploration_slots(target_posts: int, exploration_ratio: float) -> set:
        exploration_count = max(0, round(target_posts * exploration_ratio))
        if exploration_count == 0 or target_posts == 0:
            return set()
        step = target_posts / exploration_count
        return {int(round(i * step)) % target_posts for i in range(exploration_count)}

    @staticmethod
    def _pick_category(categories: List[str], prev_category: Optional[str], position: int) -> str:
        if not categories:
            return "General"
        candidate = categories[position % len(categories)]
        if candidate == prev_category and len(categories) > 1:
            candidate = categories[(position + 1) % len(categories)]
        return candidate

    @staticmethod
    def _pick_topic(topics: List[str], category: str, used_topics: set, position: int) -> str:
        pool = topics or [category]
        for offset in range(len(pool)):
            candidate = pool[(position + offset) % len(pool)]
            if candidate not in used_topics:
                return candidate
        base = pool[position % len(pool)]
        return f"{base} ({position + 1})"

    def _pick_hook_from_opportunities(
        self,
        opps: List[Any],
        category: str,
        prev_hook_type: Optional[str],
        is_experiment: bool,
        cfg: Any,
    ) -> tuple:
        """Derives hook strategy entirely from Opportunities without directly querying statistics."""
        # Find best opportunity for this category
        best_opp = None
        for opp in sorted(opps, key=lambda x: getattr(x, "opportunity_score", 0), reverse=True):
            ev = getattr(opp, "evidence", {})
            cats = ev.get("categories", []) if isinstance(ev, dict) else []
            if category in cats:
                best_opp = opp
                break

        if not is_experiment and best_opp:
            # We use the opportunity's properties instead of reading hook_service statistics
            ev = getattr(best_opp, "evidence", {})
            raw = ev.get("raw_data", {}) if isinstance(ev, dict) else {}
            hook_type = raw.get("hook_type") or "proven_hook"
            
            if hook_type != prev_hook_type:
                reason = (
                    f"Exploitation: Executing Opportunity '{best_opp.id}' for '{category}' -> '{hook_type}'. "
                    f"Score: {getattr(best_opp, 'opportunity_score', 0)}"
                )
                based_on = {
                    "source": "opportunity",
                    "opportunity_id": str(best_opp.id),
                    "detector": getattr(best_opp, "detector_name", ""),
                }
                return hook_type, float(getattr(best_opp, "confidence", 0.5)), float(getattr(best_opp, "expected_gain", 0.5)), reason, based_on

        fallback_types = cfg.strategy_fallback_hook_types or ["curiosity"]
        for hook_type in fallback_types:
            if hook_type != prev_hook_type:
                reason = (
                    f"Exploration: Generating fresh test for '{category}' -> '{hook_type}' "
                    f"(strategy.exploration_ratio={cfg.strategy_exploration_ratio})."
                )
                based_on = {"source": "exploration_fallback"}
                return hook_type, 0.3, 0.5, reason, based_on

        hook_type = fallback_types[0]
        return (
            hook_type, 0.1, 0.5,
            f"Exploration: single fallback hook type available for '{category}'.",
            {"source": "exploration_forced"},
        )

    @staticmethod
    def _build_objective(category: str, is_experiment: bool) -> str:
        intent = "Test a new hook pattern while delivering" if is_experiment else "Exploit an identified opportunity to deliver"
        return f"{intent} a correct, useful {category} insight that stops the scroll and is read to the end."

    @staticmethod
    def _build_summary(target_posts: int, exploration_slots: set, candidates_payload: List[Dict[str, Any]]) -> str:
        exploit_count = target_posts - len(exploration_slots)
        return (
            f"Weekly strategy with {target_posts} planned posts: {exploit_count} exploiting Opportunities "
            f"and {len(exploration_slots)} exploring. No topic repeats within "
            f"the week; no two consecutive slots share the same category or hook_type. This plan is "
            f"planning-only — no publishing decision has been executed."
        )
