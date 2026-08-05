from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select

from database.client import get_session
from database.models import KnowledgeRule, KnowledgeVersion, RuleLifecycleEvent
from database.repositories.base_repository import BaseRepository


class KnowledgeVersionsRepository(BaseRepository[KnowledgeVersion]):
    model = KnowledgeVersion

    def get_active(self) -> Optional[KnowledgeVersion]:
        with get_session() as session:
            stmt = select(KnowledgeVersion).where(KnowledgeVersion.is_active.is_(True))
            return session.scalars(stmt).first()


class KnowledgeRulesRepository(BaseRepository[KnowledgeRule]):
    model = KnowledgeRule

    def list_active(self) -> List[KnowledgeRule]:
        with get_session() as session:
            stmt = select(KnowledgeRule).where(KnowledgeRule.lifecycle_state == "active")
            return list(session.scalars(stmt).all())

    def list_by_state(self, lifecycle_state: str) -> List[KnowledgeRule]:
        with get_session() as session:
            stmt = select(KnowledgeRule).where(KnowledgeRule.lifecycle_state == lifecycle_state)
            return list(session.scalars(stmt).all())

    def transition_state(self, rule_id: uuid.UUID, to_state: str, reason: Optional[str] = None) -> Optional[KnowledgeRule]:
        """Moves a rule to a new lifecycle_state and records the transition
        in rule_lifecycle_events in the same transaction, so the audit trail
        can never drift from the rule's current state."""
        with get_session() as session:
            rule = session.get(KnowledgeRule, rule_id)
            if rule is None:
                return None
            from_state = rule.lifecycle_state
            rule.lifecycle_state = to_state
            session.add(RuleLifecycleEvent(rule_id=rule_id, from_state=from_state, to_state=to_state, reason=reason))
            session.flush()
            session.refresh(rule)
            return rule


class RuleLifecycleEventsRepository(BaseRepository[RuleLifecycleEvent]):
    model = RuleLifecycleEvent

    def list_for_rule(self, rule_id: uuid.UUID) -> List[RuleLifecycleEvent]:
        with get_session() as session:
            stmt = select(RuleLifecycleEvent).where(RuleLifecycleEvent.rule_id == rule_id).order_by(
                RuleLifecycleEvent.occurred_at.asc()
            )
            return list(session.scalars(stmt).all())


knowledge_versions_repository = KnowledgeVersionsRepository()
knowledge_rules_repository = KnowledgeRulesRepository()
rule_lifecycle_events_repository = RuleLifecycleEventsRepository()
