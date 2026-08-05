from __future__ import annotations
import logging
from typing import List, Optional, Any, Dict

from database.models import KnowledgeRule, KnowledgeVersion
from core.container import container
from core.events import KnowledgeUpdated, MetricsCollected, RuleActivated

logger = logging.getLogger(__name__)


class KnowledgeService:
    def __init__(
        self,
        knowledge_rules_repository=None,
        knowledge_versions_repository=None,
        rule_lifecycle_events_repository=None,
        event_bus=None,
    ) -> None:
        self.knowledge_rules_repository = knowledge_rules_repository or container.resolve("knowledge_rules_repository")
        self.knowledge_versions_repository = knowledge_versions_repository or container.resolve("knowledge_versions_repository")
        self.rule_lifecycle_events_repository = rule_lifecycle_events_repository or container.resolve("rule_lifecycle_events_repository")
        self.event_bus = event_bus or container.resolve("event_bus")

    def get_active_rules(self, category: Optional[str] = None) -> List[KnowledgeRule]:
        rules = self.knowledge_rules_repository.list_active()
        if category:
            rules = [r for r in rules if getattr(r, "category", None) == category]
        return rules

    def get_top_topic_names(
        self,
        limit: int = 5,
        fallback: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Return the names of the top topics ordered by weight.
        WeeklyPlanningEngine calls this instead of querying topics_repository directly.
        Falls back to provided fallback list (or a hardened default) when no topics exist.
        """
        _fallback = fallback or ["Tech", "Design", "AI Updates"]
        try:
            from core.container import container
            topics_repo = container.resolve("topics_repository")
            if hasattr(topics_repo, "list_ordered_by_weight"):
                rows = topics_repo.list_ordered_by_weight(limit=limit)
            else:
                rows = topics_repo.list_all()[:limit]
            names = [getattr(t, "name", "General") for t in rows]
            return names if names else _fallback
        except Exception:
            return _fallback

    def get_rule_with_history(self, rule_id: Any) -> Dict[str, Any]:
        rule = self.knowledge_rules_repository.get_by_id(rule_id)
        if not rule:
            return {}
        events = self.rule_lifecycle_events_repository.list_for_rule(rule_id)
        return {"rule": rule, "lifecycle_events": events}

    def create_rule(self, name: str, conditions: Dict[str, Any], action: Dict[str, Any], **kwargs) -> KnowledgeRule:
        rule = self.knowledge_rules_repository.create(
            name=name, conditions=conditions, action=action, lifecycle_state="proposed", **kwargs
        )
        return rule

    def update_rule_confidence(self, rule_id: Any, new_confidence: float, reason: str) -> Optional[KnowledgeRule]:
        rule = self.knowledge_rules_repository.get_by_id(rule_id)
        if not rule:
            logger.error(f"Rule {rule_id} not found.")
            return None

        rule = self.knowledge_rules_repository.update(rule_id, confidence=new_confidence)
        return rule

    def transition_rule_state(self, rule_id: Any, to_state: str, reason: str) -> Optional[KnowledgeRule]:
        valid_transitions = {
            "proposed": ["active", "retired"],
            "active": ["suspended", "retired"],
            "suspended": ["active", "retired"],
            "retired": [],
        }
        rule = self.knowledge_rules_repository.get_by_id(rule_id)
        if not rule:
            return None
        if to_state not in valid_transitions.get(rule.lifecycle_state, []):
            logger.error(f"Invalid transition from {rule.lifecycle_state} to {to_state}")
            raise ValueError(f"Invalid transition from {rule.lifecycle_state} to {to_state}")

        rule = self.knowledge_rules_repository.transition_state(rule_id, to_state, reason=reason)

        if to_state == "active" and rule is not None:
            self.event_bus.publish(RuleActivated(rule_id=rule.id, reason=reason))

        return rule

    def get_rules_by_confidence_range(self, min_conf: float, max_conf: float) -> List[KnowledgeRule]:
        rules = self.knowledge_rules_repository.list_all()
        return [r for r in rules if r.confidence is not None and min_conf <= r.confidence <= max_conf]

    def get_knowledge_statistics(self) -> Dict[str, Any]:
        rules = self.knowledge_rules_repository.list_all()
        stats: Dict[str, Any] = {"counts_per_state": {}, "total": len(rules), "avg_confidence": 0}
        total_conf, conf_count = 0, 0
        for r in rules:
            stats["counts_per_state"][r.lifecycle_state] = stats["counts_per_state"].get(r.lifecycle_state, 0) + 1
            if r.confidence is not None:
                total_conf += r.confidence
                conf_count += 1
        if conf_count > 0:
            stats["avg_confidence"] = total_conf / conf_count
        return stats

    def create_knowledge_version(self, summary: str) -> KnowledgeVersion:
        version = self.knowledge_versions_repository.create(summary=summary)
        self.event_bus.publish(KnowledgeUpdated(knowledge_version_id=version.id, summary=summary))
        return version

    def expire_low_confidence_rules(self, threshold: float = 0.3) -> int:
        count = 0
        for r in self.knowledge_rules_repository.list_by_state("active"):
            if r.confidence is not None and r.confidence < threshold:
                self.transition_rule_state(r.id, "retired", "Expired due to low confidence")
                count += 1
        return count

    # --- Event Bus subscribers -------------------------------------------------
    def on_metrics_collected(self, event: MetricsCollected) -> None:
        """Reacts to MetricsCollected. Placeholder seam for the future
        learning loop — intentionally does not implement any rule logic
        yet, only the wiring that lets it react."""
        logger.info("KnowledgeService: metrics collected for post %s (period=%s)", event.post_id, event.period)


knowledge_service = KnowledgeService()
