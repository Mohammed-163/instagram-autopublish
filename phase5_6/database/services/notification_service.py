from __future__ import annotations
import logging
from typing import List, Optional, Any, Dict

from database.models import Notification
from core.container import container
from core.events import KnowledgeUpdated, RuleActivated

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, notifications_repository=None, event_bus=None) -> None:
        self.notifications_repository = notifications_repository or container.resolve("notifications_repository")
        self.event_bus = event_bus or container.resolve("event_bus")

    def send(
        self,
        channel: str,
        message: str,
        title: Optional[str] = None,
        severity: str = "info",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        return self.notifications_repository.create(
            channel=channel,
            message=message,
            title=title,
            severity=severity,
            metadata_info=metadata or {},
            status="pending",
        )

    def list_pending(self) -> List[Notification]:
        return self.notifications_repository.list_pending()

    def mark_sent(self, notification_id: Any) -> None:
        self.notifications_repository.mark_sent(notification_id)

    def mark_failed(self, notification_id: Any) -> None:
        self.notifications_repository.mark_failed(notification_id)

    def get_recent(self, limit: int = 50) -> List[Notification]:
        ns = self.notifications_repository.list_all()
        return sorted(ns, key=lambda x: x.created_at, reverse=True)[:limit]

    # --- Event Bus subscribers -------------------------------------------------
    def on_knowledge_updated(self, event: KnowledgeUpdated) -> None:
        self.send(
            channel="telegram",
            title="Knowledge base updated",
            message=event.summary or "A new knowledge version was created.",
            severity="info",
        )

    def on_rule_activated(self, event: RuleActivated) -> None:
        self.send(
            channel="telegram",
            title="Rule activated",
            message=f"Rule {event.rule_id} is now active. {event.reason or ''}".strip(),
            severity="info",
        )


notification_service = NotificationService()
