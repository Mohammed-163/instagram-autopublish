from __future__ import annotations
import logging
from typing import List, Optional, Any, Dict
from datetime import datetime

from database.models import Metric
from core.container import container
from core.events import MetricsCollected, PostPublished

logger = logging.getLogger(__name__)


class MetricsService:
    def __init__(self, metrics_repository=None, posts_repository=None, event_bus=None) -> None:
        self.metrics_repository = metrics_repository or container.resolve("metrics_repository")
        self.posts_repository = posts_repository or container.resolve("posts_repository")
        self.event_bus = event_bus or container.resolve("event_bus")

    def record_snapshot(self, post_id: Any, period: str, captured_at: datetime, **metrics: Any) -> None:
        self.metrics_repository.upsert_snapshot(post_id, period, captured_at, **metrics)

        self.event_bus.publish(MetricsCollected(post_id=post_id, period=period, metrics=dict(metrics)))

    def get_post_metrics(self, post_id: Any) -> List[Metric]:
        return self.metrics_repository.list_for_post(post_id)

    def get_latest_for_post(self, post_id: Any) -> Optional[Metric]:
        """
        Return the most-recent metric snapshot for a post.
        Used by ObjectiveEngine to build the success score.
        """
        if hasattr(self.metrics_repository, "get_latest_for_post"):
            return self.metrics_repository.get_latest_for_post(post_id)
        rows = self.metrics_repository.list_for_post(post_id)
        return rows[0] if rows else None

    def get_best_posts(self, period: str = "24h", metric: str = "reach", limit: int = 10) -> List[Dict[str, Any]]:
        all_metrics = [
            m for m in self.metrics_repository.list_all() if m.snapshot_period == period
        ]
        sorted_metrics = sorted(all_metrics, key=lambda m: getattr(m, metric, 0) or 0, reverse=True)[:limit]
        return [{"post_id": m.post_id, metric: getattr(m, metric, None)} for m in sorted_metrics]

    def get_category_performance(self, days: int = 30) -> Dict[str, Any]:
        return {"category": "performance"}

    def get_engagement_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        return []

    def refresh_topic_stats(self, topic_id: Any) -> None:
        logger.info(f"Refreshed stats for topic {topic_id}")

    # --- Event Bus subscribers -------------------------------------------------
    def on_post_published(self, event: PostPublished) -> None:
        """Reacts to PostPublished. Doesn't reach back into PostService —
        it only knows about the event payload."""
        logger.info("MetricsService: tracking started for post %s", event.post_id)


metrics_service = MetricsService()
