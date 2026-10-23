"""
HookStructureLearningEngine
============================
Phase 4 Part 2 — item 1 (Hook Structure Learning Engine) + item 2 (Plugin
Architecture) + item 3 (Hook Grammar foundation) + item 4 (Feature
Importance foundation, exposed via HookStructureService but not invoked
here) + item 7 (Explainability).

Responsibility:
- Listen to HookAnalyzed (emitted by HookPatternDiscoveryEngine, which has
  already isolated the hook — the first line — and classified its type).
- Run every discovered Hook Feature Analyzer plugin against the hook text.
  Each analyzer is fully independent (engines/hook_feature_analyzers) and
  is discovered dynamically via pkgutil — this engine never imports a
  specific analyzer by name and never hard-codes which features matter.
- Fold the analyzers' boolean/positional outputs into a simple, ordered
  `grammar_sequence` (foundation for the future Hook Grammar Graph — see
  engines/hook_grammar.py).
- Persist a HookStructure row (all features + full explainability) and one
  HookFeatureValue row per feature, via HookStructureService.
- Emit HookFeatureExtracted -> HookFeaturesStored -> HookStructureLearned.

This engine does NOT judge whether a hook worked and does NOT compute
Feature Importance — that requires the post's success score, which only
exists downstream. It only learns and records STRUCTURE.

Design:
- Extends EngineBase — depends on HookStructureService only, never on
  repositories.
- Deterministic: given the same hook_text and the same analyzer versions,
  running this engine twice produces identical features/explainability/
  grammar_sequence (required for Replay Support).
"""
from __future__ import annotations

import importlib
import hashlib
import inspect
import logging
import pkgutil
from typing import Any, Dict, List, Tuple

from core.events import HookAnalyzed, HookFeatureExtracted, HookFeaturesStored, HookStructureLearned
from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)

# Fixed, documented ordering used only to make `grammar_sequence` stable
# and readable. This is NOT a success rule — it never decides which
# component "wins", only in what order detected components are listed.
_GRAMMAR_COMPONENT_ORDER: Tuple[str, ...] = (
    "curiosity", "question", "number", "percentage", "negation",
    "warning", "comparison", "promise", "time_reference",
    "emotional", "scientific", "historical", "psychology", "human_body",
)

_GRAMMAR_FEATURE_MAP: Dict[str, str] = {
    "curiosity": "has_curiosity_word",
    "question": "has_question",
    "number": "has_number",
    "percentage": "has_percentage",
    "negation": "has_negation",
    "warning": "has_warning_word",
    "comparison": "has_comparison",
    "promise": "has_promise",
    "time_reference": "has_time_reference",
    "emotional": "has_emotional_word",
    "scientific": "has_scientific_word",
    "historical": "has_historical_word",
    "psychology": "has_psychology_word",
    "human_body": "has_human_body_word",
}


class HookStructureLearningEngine(EngineBase):
    """Converts HookAnalyzed -> HookFeatureExtracted -> HookFeaturesStored
    -> HookStructureLearned. Purely statistical / rule-based feature
    extraction via independently pluggable analyzers; no LLM calls."""

    ENGINE_NAME = "hook_structure_learning"

    def __init__(
        self,
        event_bus: Any,
        hook_structure_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
        analyzers: List[HookFeatureAnalyzer] = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.hook_structure_service = hook_structure_service
        self.analyzers: List[HookFeatureAnalyzer] = (
            analyzers if analyzers is not None else self._discover_analyzers()
        )

    # ------------------------------------------------------------------ plugin discovery
    @staticmethod
    def _discover_analyzers() -> List[HookFeatureAnalyzer]:
        """Discover every HookFeatureAnalyzer plugin under
        engines.hook_feature_analyzers.plugins. Adding a new analyzer
        module there is automatically picked up — no change needed here."""
        import engines.hook_feature_analyzers.plugins as plugins_pkg

        discovered: List[HookFeatureAnalyzer] = []
        prefix = plugins_pkg.__name__ + "."
        for _importer, modname, ispkg in pkgutil.walk_packages(plugins_pkg.__path__, prefix):
            if ispkg:
                continue
            module = importlib.import_module(modname)
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, HookFeatureAnalyzer)
                    and obj is not HookFeatureAnalyzer
                    and obj.__module__ == modname  # only classes DEFINED in this module
                ):
                    instance = obj()
                    discovered.append(instance)
                    logger.info("[HookStructureLearningEngine] Loaded analyzer plugin: %s v%s", name, instance.version)

        # Sort by feature_name for a fully deterministic analyzer order
        # (Replay Support: iteration order must never depend on filesystem
        # discovery order, which is not guaranteed stable across systems).
        discovered.sort(key=lambda a: a.feature_name)
        return discovered

    # ------------------------------------------------------------------ event handler
    def handle_hook_analyzed(self, event: HookAnalyzed) -> None:
        try:
            hook_text = event.hook_text or ""
            category = event.category or "General"

            features, explainability = self._run_analyzers(hook_text)
            grammar_sequence = self.build_grammar_sequence(features)
            structural_fingerprint, feature_fingerprint, fingerprint_hash = self._generate_fingerprints(grammar_sequence, features)

            self.event_bus.publish(
                HookFeatureExtracted(
                    post_id=event.post_id,
                    hook_text=hook_text,
                    features=features,
                    explainability=explainability,
                )
            )

            analyzer_versions = {a.feature_name: a.version for a in self.analyzers}

            structure = self.hook_structure_service.record_hook_structure(
                post_id=event.post_id,
                hook_text=hook_text,
                features=features,
                explainability=explainability,
                grammar_sequence=grammar_sequence,
                analyzer_versions=analyzer_versions,
                category=category,
                hook_type=event.hook_type,
                structural_fingerprint=structural_fingerprint,
                feature_fingerprint=feature_fingerprint,
                fingerprint_hash=fingerprint_hash,
            )

            self.hook_structure_service.record_feature_values(
                hook_structure_id=structure.id,
                post_id=event.post_id,
                features=features,
                explainability=explainability,
            )

            self.event_bus.publish(
                HookFeaturesStored(
                    structure_id=structure.id,
                    post_id=event.post_id,
                    feature_count=len(features),
                )
            )

            self.event_bus.publish(
                HookStructureLearned(
                    structure_id=structure.id,
                    post_id=event.post_id,
                    category=category,
                    hook_type=event.hook_type,
                    grammar_sequence=grammar_sequence,
                    feature_count=len(features),
                    structural_fingerprint=structural_fingerprint,
                    feature_fingerprint=feature_fingerprint,
                    fingerprint_hash=fingerprint_hash,
                )
            )

            self.heartbeat("healthy")
            logger.info(
                "[HookStructureLearningEngine] post=%s features=%d grammar=%s",
                event.post_id, len(features), grammar_sequence,
            )

        except Exception as e:
            logger.exception("[HookStructureLearningEngine] Error learning hook structure: %s", e)
            self.heartbeat("error", error=str(e))

    # ------------------------------------------------------------------ analyzer execution
    def _run_analyzers(self, hook_text: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        features: Dict[str, Any] = {}
        explainability: Dict[str, Any] = {}

        for analyzer in self.analyzers:
            try:
                result = analyzer.analyze(hook_text)
                features[analyzer.feature_name] = result.get("value")
                explainability[analyzer.feature_name] = {
                    "extraction_method": result.get("extraction_method", "unknown"),
                    "source": result.get("source", "hook_text"),
                    "analyzer": type(analyzer).__name__,
                    "analyzer_version": analyzer.version,
                }
            except Exception as e:
                # A single broken plugin must never break structure learning
                # for the rest of the features.
                logger.warning(
                    "[HookStructureLearningEngine] Analyzer %s failed: %s",
                    type(analyzer).__name__, e,
                )

        return features, explainability

    # ------------------------------------------------------------------ grammar sequence (foundation only)
    @staticmethod
    def build_grammar_sequence(features: Dict[str, Any]) -> List[str]:
        """Build the simple, ORDERED grammar_sequence foundation described
        in engines/hook_grammar.py. Always starts with 'opening'; then
        appends every component whose backing feature is present, in the
        fixed, documented order of _GRAMMAR_COMPONENT_ORDER (not a success
        ranking — purely a stable, readable ordering)."""
        sequence = ["opening"]
        for component in _GRAMMAR_COMPONENT_ORDER:
            feature_name = _GRAMMAR_FEATURE_MAP[component]
            raw = features.get(feature_name)
            present = raw.get("present") if isinstance(raw, dict) else bool(raw)
            if present:
                sequence.append(component)
        return sequence

    # ------------------------------------------------------------------ fingerprint generation
    @staticmethod
    def _generate_fingerprints(grammar_sequence: List[str], features: Dict[str, Any]) -> Tuple[str, str, str]:
        """Generates a two-layer fingerprint to identify structurally identical or feature-identical hooks."""
        # 1. Structural Fingerprint (e.g. curiosity+question+number)
        structural_fingerprint = "+".join(grammar_sequence)

        # 2. Feature Fingerprint (sorted list of all present features)
        present_features = []
        for feature_name, raw_value in features.items():
            present = raw_value.get("present") if isinstance(raw_value, dict) else bool(raw_value)
            if present:
                present_features.append(feature_name)
        
        present_features.sort()
        feature_fingerprint = "+".join(present_features) if present_features else "none"

        # 3. Combined Hash
        combined = f"{structural_fingerprint}|{feature_fingerprint}"
        fingerprint_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()

        return structural_fingerprint, feature_fingerprint, fingerprint_hash
