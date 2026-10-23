from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


class WeeklyPerformanceReviewEngine:
    def __init__(self, metrics_repository: Any, hook_structure_repository: Any,
                 topics_repository: Any, weekly_planning_service: Any,
                 gemini_client: Any, posts_repository: Any = None,
                 media_repository: Any = None,
                 hook_feature_values_repository: Any = None) -> None:
        self.metrics_repository = metrics_repository
        self.hook_structure_repository = hook_structure_repository
        self.topics_repository = topics_repository
        self.weekly_planning_service = weekly_planning_service
        self.gemini_client = gemini_client
        from database.repositories.media_repository import MediaRepository
        from database.repositories.posts_repository import PostsRepository
        from database.repositories.hook_structure_repository import HookFeatureValuesRepository
        self.posts_repository = posts_repository or PostsRepository()
        self.media_repository = media_repository or MediaRepository()
        self.hook_feature_values_repository = hook_feature_values_repository or HookFeatureValuesRepository()

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    @staticmethod
    def _period_rank(period: str) -> int:
        return {"7d": 4, "24h": 3, "6h": 2, "2h": 1}.get(period, 0)

    @staticmethod
    def _averages(values: dict[str, list[float]]) -> dict[str, float]:
        return {key: round(sum(items) / len(items), 6) if items else 0.0 for key, items in values.items()}

    def run_weekly_review(self) -> None:
        now = datetime.now(timezone.utc)
        week_start = now - timedelta(days=7)
        posts = self.posts_repository.list_by_status("published", limit=1000)
        posts = [p for p in posts if getattr(p, "published_at", None)
                 and week_start <= self._as_utc(p.published_at) <= now]
        summary: dict[str, Any] = {
            "period": {"from": week_start.isoformat(), "to": now.isoformat()},
            "posts_count": len(posts), "by_hook_type": {}, "by_background_type": {},
            "top_posts": [], "bottom_posts": [],
        }
        scored: list[dict[str, Any]] = []
        for post in posts:
            metrics = sorted(self.metrics_repository.list_for_post(post.id),
                             key=lambda m: self._period_rank(getattr(m, "snapshot_period", "")),
                             reverse=True)
            selected = metrics[0] if metrics else None
            score = float(getattr(selected, "engagement_rate", None) or 0.0)
            hooks = self.hook_structure_repository.list_for_post(post.id)
            media_rows = self.media_repository.list_for_post(post.id)
            backgrounds = [getattr(m, "background_type", None) or getattr(m, "original_image_source", None)
                           for m in media_rows]
            backgrounds = [str(v) for v in backgrounds if v]
            scored.append({"post_id": str(post.id), "published_at": self._as_utc(post.published_at).isoformat(),
                           "engagement_rate": score,
                           "snapshot_period": getattr(selected, "snapshot_period", None),
                           "hook_types": [str(getattr(h, "hook_type", "") or "") for h in hooks],
                           "background_types": backgrounds,
                           "feature_values": [
                               {"feature_name": getattr(v, "feature_name", ""),
                                "feature_value": getattr(v, "feature_value", None)}
                               for h in hooks
                               for v in self.hook_feature_values_repository.list_for_structure(h.id)
                           ]})
            for hook in hooks:
                summary["by_hook_type"].setdefault(str(getattr(hook, "hook_type", None) or "unknown"), []).append(score)
            for background in backgrounds:
                summary["by_background_type"].setdefault(background, []).append(score)
        scored.sort(key=lambda item: item["engagement_rate"], reverse=True)
        summary["top_posts"] = scored[:3]
        summary["bottom_posts"] = list(reversed(scored[-3:]))
        summary["by_hook_type"] = self._averages(summary["by_hook_type"])
        summary["by_background_type"] = self._averages(summary["by_background_type"])
        plan = self.gemini_client.build_weekly_plan(summary)
        plan_id = uuid.uuid4()
        self.weekly_planning_service.create_plan(plan_id=plan_id, week_start=now,
            week_end=now + timedelta(days=7), plan_data=plan, status="draft")
        self.weekly_planning_service.activate_plan(plan_id)
        logger.info("Weekly performance review completed and plan activated: %s", plan_id)
