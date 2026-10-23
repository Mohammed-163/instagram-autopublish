from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from core.events import MetricNormalized, SuccessScoreCalculated
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)

class ObjectiveEngine(EngineBase):
    ENGINE_NAME = "objective"

    def __init__(
        self,
        event_bus: Any,
        metrics_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.metrics_service = metrics_service

    def handle_metric_normalized(self, event: MetricNormalized) -> None:
        try:
            post_id = event.post_id
            # Retrieve latest metrics for post (simulated here)
            metrics = self.metrics_service.get_latest_for_post(post_id) if hasattr(self.metrics_service, 'get_latest_for_post') else {}
            
            # Dynamic weights from settings (e.g. Growth Profile)
            profile = getattr(self.settings, "objective_profile", "Balanced")
            weights = getattr(self.settings, "objective_weights", {"views": 0.2, "watch_time": 0.5, "shares": 0.3})
            
            score = 0.0
            explanation = []
            
            for metric, weight in weights.items():
                val = float(metrics.get(metric, 0.0) if isinstance(metrics, dict) else getattr(metrics, metric, 0.0))
                contribution = val * weight
                score += contribution
                explanation.append(f"{metric}: {val} * {weight} = {contribution}")
                
            explainability = {
                "summary": " + ".join(explanation),
                "details": explanation
            }
            
            calc_event = SuccessScoreCalculated(
                post_id=post_id,
                score=score,
                explainability=explainability,
                objective_version="1.0",
                objective_profile=profile,
                weight_config_version="1.0",
                settings_version="1.0"
            )
            
            self.event_bus.publish(calc_event)
            self.heartbeat("healthy")
            
        except Exception as e:
            logger.exception("Error in ObjectiveEngine")
            self.heartbeat("error", error=str(e))
