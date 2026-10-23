from __future__ import annotations
import logging
from typing import List, Optional, Any, Dict
from decimal import Decimal

from database.models import Feature
from core.container import container

logger = logging.getLogger(__name__)


class FeatureService:
    def __init__(self, features_repository=None) -> None:
        self.features_repository = features_repository or container.resolve("features_repository")

    def extract_feature(self, post_id: Any, key: str, value: Any, source: Optional[str] = None) -> None:
        self.features_repository.upsert_feature(post_id, key, feature_value=value, source=source)

    def get_features(self, post_id: Any) -> List[Feature]:
        return self.features_repository.list_for_post(post_id)

    def get_feature_value(self, post_id: Any, key: str) -> Optional[Decimal]:
        feature = self.features_repository.get_feature(post_id, key)
        return Decimal(str(feature.feature_value)) if feature else None

    def bulk_extract_features(self, post_id: Any, features: Dict[str, Any]) -> None:
        for k, v in features.items():
            self.features_repository.upsert_feature(post_id, k, feature_value=v)

    def upsert_features(
        self,
        post_id: Any,
        features: Dict[str, Any],
        source: str = "feature_extraction_engine",
    ) -> None:
        """Persist a complete set of features for a post in a single call."""
        for key, value in features.items():
            self.features_repository.upsert_feature(
                post_id=post_id,
                feature_key=key,
                feature_value=float(value),
                feature_value_text=str(value),
                source=source,
            )
        logger.debug("[FeatureService] Upserted %d features for post %s", len(features), post_id)

    def get_feature_map(self, post_id: Any) -> Dict[str, float]:
        """
        Return {feature_key: feature_value} dict for a post.
        Convenient for pattern analysis without iterating model objects.
        """
        rows = self.features_repository.get_features_for_post(post_id) if hasattr(
            self.features_repository, "get_features_for_post"
        ) else self.features_repository.list_for_post(post_id)
        return {
            getattr(r, "feature_key", ""): float(getattr(r, "feature_value", 0.0))
            for r in rows
        }


feature_service = FeatureService()
