"""
RuleEvolutionService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from ..config.settings import Settings
from ..domain.enums import RuleStatus
from ..domain.models import Rule
from ..events import EventPublisher, RuleEvolved
from ..fingerprint import compute_fingerprint
from ..repositories.rule_repository import RuleRepository


class RuleEvolutionService:
    """Proposes, activates, and decays rules within a bounded rule population."""

    def __init__(self, repository: RuleRepository, settings: Settings,
                 publisher: EventPublisher) -> None:
        self._repository = repository
        self._settings = settings
        self._publisher = publisher

    def propose(self, key: str, condition_expression: str, action_expression: str,
                confidence: float, generation: int = 0) -> Rule:
        if self._repository.count_active() >= self._settings.rule_evolution_max_rules:
            status = RuleStatus.PROPOSED
        else:
            status = RuleStatus.ACTIVE if confidence >= self._settings.rule_confidence_decay else RuleStatus.PROPOSED

        payload = {
            "key": key, "condition_expression": condition_expression,
            "action_expression": action_expression, "confidence": confidence,
            "generation": generation,
        }
        fp = compute_fingerprint(payload)

        rule = Rule(
            id=None, key=key, condition_expression=condition_expression,
            action_expression=action_expression, status=status, confidence=confidence,
            generation=generation, fingerprint=fp,
        )
        stored = self._repository.add(rule)

        self._publisher.publish(RuleEvolved(
            subject_key=stored.key, fingerprint=stored.fingerprint,
            payload={"status": stored.status.value},
        ))
        return stored

    def decay(self, rule: Rule) -> Rule:
        new_confidence = max(0.0, round(rule.confidence - self._settings.rule_confidence_decay, 10))
        new_status = RuleStatus.DEPRECATED if new_confidence <= 0.0 else rule.status
        self._repository.update_confidence_and_status(rule.key, new_confidence, new_status)
        return self._repository.get_by_key(rule.key)
