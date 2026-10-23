from __future__ import annotations

import logging
import uuid
import importlib
import pkgutil
import inspect
from typing import Any, Dict, List

from core.events import MetricNormalized, FeaturesExtracted, ObservationRecorded
from engines.shared.engine_base import EngineBase
from engines.extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

class FeatureExtractionEngine(EngineBase):
    ENGINE_NAME = "feature_extraction"

    def __init__(
        self,
        event_bus: Any,
        post_service: Any,
        feature_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.post_service = post_service
        self.feature_service = feature_service
        self.extractors: List[BaseExtractor] = []
        self._load_extractors()

    def _load_extractors(self):
        import engines.extractors as extractors_pkg
        prefix = extractors_pkg.__name__ + "."
        for importer, modname, ispkg in pkgutil.walk_packages(extractors_pkg.__path__, prefix):
            if not ispkg:
                module = importlib.import_module(modname)
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseExtractor) and obj is not BaseExtractor:
                        self.extractors.append(obj())
                        logger.info(f"Loaded extractor: {name} v{obj().version}")

    def handle_metric_normalized(self, event: MetricNormalized) -> None:
        self._process(event.post_id)
        
    def handle_observation_recorded(self, event: ObservationRecorded) -> None:
        self._process(event.post_id)

    def _process(self, post_id: uuid.UUID) -> None:
        try:
            logger.info("[FeatureExtractionEngine] Extracting features for post %s", post_id)

            features_dict: Dict[str, Any] = {}
            lineage_dict: Dict[str, Any] = {}

            post = self.post_service.get_by_id(post_id)
            design = self.post_service.get_design_for_post(post_id)
            metrics = {} # fetch from metric history in real implementation

            for extractor in self.extractors:
                try:
                    result = extractor.extract(post, design, metrics)
                    features_dict[extractor.feature_name] = result["value"]
                    lineage_dict[extractor.feature_name] = {
                        "extractor": type(extractor).__name__,
                        "version": extractor.version,
                        "extras": result.get("lineage_extras", {})
                    }
                except Exception as e:
                    logger.warning(f"Extractor {extractor.feature_name} failed: {e}")

            # Persist via FeatureService
            self.feature_service.upsert_features(post_id, features_dict) # would include lineage in future

            features_event = FeaturesExtracted(post_id=post_id, features=features_dict)
            self.event_bus.publish(features_event)

            self.heartbeat("healthy")
        except Exception as e:
            logger.exception("[FeatureExtractionEngine] Error %s", e)
            self.heartbeat("error", error=str(e))
