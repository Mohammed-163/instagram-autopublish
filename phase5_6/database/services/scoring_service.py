"""
ScoringService
==============
Service layer for post score persistence.

Responsibility:
- Upsert individual score dimensions for a post.
- Retrieve the latest score set for a post.
- Provide a convenience method that persists a full scores dictionary.

Engines interact with scores exclusively through this service; they never
touch scores_repository directly.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from core.container import container

logger = logging.getLogger(__name__)


class ScoringService:
    def __init__(self, scores_repository: Any = None) -> None:
        self.scores_repository = scores_repository or container.resolve("scores_repository")

    def upsert_scores(
        self,
        post_id: uuid.UUID,
        scores: Dict[str, float],
        method_version: str = "1.0",
    ) -> None:
        """Persist all score dimensions for a post in a single call."""
        for score_type, score_value in scores.items():
            self.scores_repository.upsert_score(
                post_id=post_id,
                score_type=score_type,
                score_value=score_value,
                method_version=method_version,
            )
        logger.debug("[ScoringService] Upserted %d scores for post %s", len(scores), post_id)

    def get_scores_for_post(self, post_id: uuid.UUID) -> List[Any]:
        """Return all score rows for a post."""
        if hasattr(self.scores_repository, "get_scores_for_post"):
            return self.scores_repository.get_scores_for_post(post_id)
        return []

    def get_score_map(self, post_id: uuid.UUID) -> Dict[str, float]:
        """Return {score_type: score_value} dict for a post — convenient for pattern analysis."""
        rows = self.get_scores_for_post(post_id)
        return {
            getattr(r, "score_type", ""): float(getattr(r, "score_value", 0.0))
            for r in rows
        }


scoring_service = ScoringService()
