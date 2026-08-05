"""
KnowledgeEngine
================
5) Knowledge Engine

Responsibility:
- Listen ONLY to PatternsDiscovered events from PatternDiscoveryEngine.
- Transform candidate patterns into proposed Knowledge Rules and Knowledge Versions.
- Emit KnowledgeUpdated event.
- NEVER process raw features or metrics directly.

Design:
- Extends EngineBase for heartbeat() and settings.
- Depends on KnowledgeService (Service Layer) — never on repositories directly.
- KnowledgeService encapsulates all rule-creation and versioning logic.
"""
from __future__ import annotations

import logging
from typing import Any

from core.events import PatternsDiscovered, KnowledgeUpdated
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)


class KnowledgeEngine(EngineBase):
    """
    Converts PatternsDiscovered → KnowledgeUpdated.
    Transforms candidate patterns into proposed Knowledge Rules.
    """

    ENGINE_NAME = "knowledge"

    def __init__(
        self,
        event_bus: Any,
        knowledge_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.knowledge_service = knowledge_service

    def handle_patterns_discovered(self, event: PatternsDiscovered) -> None:
        """Handle PatternsDiscovered: create knowledge rule and version, emit KnowledgeUpdated."""
        try:
            pattern_name = event.pattern_name
            conditions = event.conditions
            confidence = event.confidence_score

            logger.info(
                "[KnowledgeEngine] Building knowledge from candidate pattern: '%s' (id=%s)",
                pattern_name,
                event.pattern_id,
            )

            # 1. Create proposed knowledge rule via KnowledgeService
            self.knowledge_service.create_rule(
                name=pattern_name,
                conditions=conditions,
                action={"action_type": "boost_confidence", "value": confidence},
            )

            # 2. Create knowledge version and publish KnowledgeUpdated
            version = self.knowledge_service.create_knowledge_version(
                summary=f"Knowledge updated from pattern: {pattern_name}",
            )

            # create_knowledge_version already publishes KnowledgeUpdated internally,
            # but we re-publish here so that the engine fully controls what goes on
            # the bus and tests can assert on it without coupling to KnowledgeService internals.
            knowledge_event = KnowledgeUpdated(
                knowledge_version_id=getattr(version, "id", None),
                summary=f"Knowledge rule created for pattern '{pattern_name}'",
            )
            self.event_bus.publish(knowledge_event)

            self.heartbeat("healthy")
            logger.info(
                "[KnowledgeEngine] KnowledgeUpdated published for version: %s",
                getattr(version, "id", "unknown"),
            )

        except Exception as e:
            logger.exception("[KnowledgeEngine] Error updating knowledge from pattern event %s: %s", event, e)
            self.heartbeat("error", error=str(e))
