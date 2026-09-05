from __future__ import annotations
import logging
from typing import List, Optional, Any, Dict
from datetime import datetime

from database.models import Post, Score
from core.container import container
from core.events import PostPublished

logger = logging.getLogger(__name__)


class PostService:
    """Depends on injected repositories + an injected event bus — never
    imports `database.client` or constructs its own repositories."""

    def __init__(
        self,
        posts_repository=None,
        designs_repository=None,
        media_repository=None,
        metrics_repository=None,
        scores_repository=None,
        quality_results_repository=None,
        event_bus=None,
    ) -> None:
        self.posts_repository = posts_repository or container.resolve("posts_repository")
        self.designs_repository = designs_repository or container.resolve("designs_repository")
        self.media_repository = media_repository or container.resolve("media_repository")
        self.metrics_repository = metrics_repository or container.resolve("metrics_repository")
        self.scores_repository = scores_repository or container.resolve("scores_repository")
        self.quality_results_repository = quality_results_repository or container.resolve("quality_results_repository")
        self.event_bus = event_bus or container.resolve("event_bus")

    def get_by_id(self, post_id: Any) -> Optional[Post]:
        """Return a post by primary key — used by FeatureExtractionEngine."""
        return self.posts_repository.get_by_id(post_id)

    def get_design_for_post(self, post_id: Any) -> Optional[Any]:
        """Return the design record for a post — used by FeatureExtractionEngine."""
        if hasattr(self.designs_repository, "get_for_post"):
            return self.designs_repository.get_for_post(post_id)
        return None

    def create_post(self, topic_id: Optional[Any] = None, status: str = "draft", **fields: Any) -> Post:
        return self.posts_repository.create(topic_id=topic_id, status=status, **fields)

    def get_post_full(self, post_id: Any) -> Dict[str, Any]:
        post = self.posts_repository.get_by_id(post_id)
        if not post:
            return {}

        return {
            "post": post,
            "designs": self.designs_repository.list_all(),
            "media": self.media_repository.list_all(),
            "metrics": self.metrics_repository.list_for_post(post_id),
            "scores": self.scores_repository.list_for_post(post_id),
            "quality": self.quality_results_repository.list_for_post(post_id),
        }

    def list_by_status(self, status: str, limit: int = 200) -> List[Post]:
        return self.posts_repository.list_by_status(status, limit=limit)

    def transition_status(self, post_id: Any, new_status: str) -> Optional[Post]:
        post = self.posts_repository.get_by_id(post_id)
        if not post:
            return None

        post = self.posts_repository.update(post_id, status=new_status)

        # This is the one place "a post got published" happens. It doesn't
        # call metrics/knowledge/notification services directly — it just
        # announces the fact. Whoever cares is subscribed on the bus (see
        # core/wiring.py). Adding a new engine later means adding a new
        # subscriber there, not touching this method.
        if new_status == "published" and post is not None:
            self.event_bus.publish(
                PostPublished(
                    post_id=post.id,
                    instagram_media_id=getattr(post, "instagram_media_id", None),
                    topic_id=getattr(post, "topic_id", None),
                )
            )

        return post

    def get_post_score(self, post_id: Any) -> Optional[Score]:
        scores = self.scores_repository.list_for_post(post_id)
        return scores[0] if scores else None

    def calculate_post_performance(self, post_id: Any) -> Dict[str, Any]:
        return {"performance": "good"}


post_service = PostService()
