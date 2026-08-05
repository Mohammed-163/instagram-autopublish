from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import Any, Dict, List

from core.events import KnowledgeCoverageCalculated, OpportunitiesDiscovered
from engines.opportunity_detectors.base_detector import BaseDetector
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)


class OpportunityDiscoveryEngine(EngineBase):
    """
    Phase C: Opportunity Discovery Engine.

    - Discovers all Detector plugins automatically via pkgutil
    - NO if/elif for detector type mapping
    - NO direct repository access (uses Knowledge/Coverage Services only)
    - All thresholds come from SettingsService
    - Deterministic: detectors always execute in same order, results sorted.
    """

    ENGINE_NAME = "opportunity_discovery"

    def __init__(
        self,
        event_bus: Any,
        opportunity_service: Any,
        knowledge_service: Any,
        knowledge_coverage_service: Any,
        feature_service: Any,
        settings_service: Any = None,
        health_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.opportunity_service = opportunity_service
        self.knowledge_service = knowledge_service
        self.knowledge_coverage_service = knowledge_coverage_service
        self.feature_service = feature_service
        self._detectors: List[BaseDetector] = []
        self._load_detectors()

    def _load_detectors(self) -> None:
        """Auto-discover all BaseDetector plugins via pkgutil.
        Sort by name to ensure determinism.
        """
        import engines.opportunity_detectors.plugins as plugins_pkg
        prefix = plugins_pkg.__name__ + "."
        found = []
        for _, modname, ispkg in sorted(
            pkgutil.walk_packages(plugins_pkg.__path__, prefix),
            key=lambda x: x[1],
        ):
            if not ispkg:
                try:
                    module = importlib.import_module(modname)
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (
                            issubclass(obj, BaseDetector)
                            and obj is not BaseDetector
                            and name not in [d.__class__.__name__ for d in found]
                        ):
                            found.append(obj())
                            logger.info("[OpportunityDiscoveryEngine] Loaded detector: %s v%s", obj().detector_name, obj().version)
                except Exception as e:
                    logger.warning("[OpportunityDiscoveryEngine] Failed to load module %s: %s", modname, e)
        
        # Deterministic sorting
        self._detectors = sorted(found, key=lambda d: d.detector_name)

    def handle_coverage_calculated(self, event: KnowledgeCoverageCalculated) -> None:
        """Triggered automatically when Knowledge Coverage is updated."""
        try:
            self._run_detection(coverage_snapshot_id=event.snapshot_id)
            self.heartbeat("healthy")
        except Exception as e:
            logger.exception("[OpportunityDiscoveryEngine] Error during detection: %s", e)
            self.heartbeat("error", error=str(e))

    def _run_detection(self, coverage_snapshot_id: Any = None) -> None:
        # 1. Load dynamic settings from SettingsService
        detector_settings = self._load_settings()

        # 2. Build complete knowledge context (via Services, NO DB Repos)
        knowledge_context = self._build_context()

        # 3. Run all plugins
        all_candidates = []
        for detector in self._detectors:
            try:
                candidates = detector.detect(knowledge_context, detector_settings)
                # Attach global context versions to candidates
                for c in candidates:
                    c.knowledge_version = knowledge_context.get("knowledge_version", "")
                    c.coverage_version = knowledge_context.get("coverage_version", "")
                    c.settings_version = detector_settings.get("version", "")
                all_candidates.extend(candidates)
            except Exception as e:
                logger.warning(
                    "[OpportunityDiscoveryEngine] Detector %s failed: %s",
                    detector.detector_name, e
                )

        # 4. Filter invalid candidates and sort deterministically
        valid_candidates = [c for c in all_candidates if c.is_valid()]
        valid_candidates.sort(key=lambda c: (c.detector_name, c.opportunity_type, str(c.related_entities)))

        # 5. Persist and Score (via OpportunityService + ScoringService)
        scoring_profile = detector_settings.get("scoring_profile", "Balanced")
        for candidate in valid_candidates:
            try:
                self.opportunity_service.persist_candidate(candidate, scoring_profile=scoring_profile)
            except Exception as e:
                logger.warning("[OpportunityDiscoveryEngine] Failed to persist candidate: %s", e)

        # 6. Emit OpportunitiesDiscovered Event
        top_score = max((c.opportunity_score or 0.0 for c in valid_candidates), default=0.0)
        self.event_bus.publish(
            OpportunitiesDiscovered(
                coverage_snapshot_id=coverage_snapshot_id,
                total_detected=len(valid_candidates),
                opportunity_types=sorted(list(set(c.opportunity_type for c in valid_candidates))),
                top_score=top_score,
            )
        )

    def _load_settings(self) -> Dict[str, Any]:
        """Load all detector settings from SettingsService."""
        try:
            return self._settings_service.get("opportunity_detection", {}) or {}
        except Exception:
            return {}

    def _build_context(self) -> Dict[str, Any]:
        """Build a snapshot of all data needed by detectors.
        Converts ORM objects to dicts so detectors remain isolated from DB tier.
        """
        context: Dict[str, Any] = {}
        try:
            rules = self.knowledge_service.get_active_rules()
            context["active_rules"] = [
                {
                    "id": str(getattr(r, "id", "")),
                    "category": getattr(r, "category", ""),
                    "hook_type": getattr(r, "hook_type", ""),
                    "confidence": float(getattr(r, "confidence", 0)),
                    "sample_size": int(getattr(r, "sample_size", 0)),
                    "name": getattr(r, "name", ""),
                    "outcome_scores": getattr(r, "outcome_scores", []),
                }
                for r in (rules or [])
            ]
        except Exception as e:
            logger.warning("Failed to load active rules: %s", e)
            context["active_rules"] = []

        try:
            stats = self.knowledge_service.get_knowledge_statistics()
            context["knowledge_statistics"] = stats or {}
            context["knowledge_version"] = str(stats.get("version", "")) if isinstance(stats, dict) else ""
        except Exception:
            context["knowledge_statistics"] = {}
            context["knowledge_version"] = ""

        try:
            snapshot = self.knowledge_coverage_service.get_latest_snapshot()
            if snapshot:
                context["knowledge_coverage"] = float(getattr(snapshot, "knowledge_coverage", 0))
                context["unknown_entities"] = int(getattr(snapshot, "unknown_entities", 0))
                context["coverage_version"] = getattr(snapshot, "coverage_version", "")
                cat_dist = getattr(snapshot, "category_distribution", {})
                context["all_categories"] = list(cat_dist.keys()) if cat_dist else []
            else:
                context["knowledge_coverage"] = 0.0
                context["unknown_entities"] = 0
                context["coverage_version"] = ""
                context["all_categories"] = []
        except Exception:
            context["knowledge_coverage"] = 0.0
            context["unknown_entities"] = 0
            context["coverage_version"] = ""
            context["all_categories"] = []

        hook_usage: Dict[str, int] = {}
        for r in context.get("active_rules", []):
            ht = r.get("hook_type", "")
            if ht:
                hook_usage[ht] = hook_usage.get(ht, 0) + 1
        context["hook_type_usage"] = hook_usage
        context["features_by_category"] = {}  # Extensible for later features

        return context
