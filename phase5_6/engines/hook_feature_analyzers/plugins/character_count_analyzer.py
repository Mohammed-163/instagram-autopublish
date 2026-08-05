from __future__ import annotations

from typing import Any, Dict

from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer


class CharacterCountAnalyzer(HookFeatureAnalyzer):
    @property
    def feature_name(self) -> str:
        return "character_count"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, hook_text: str) -> Dict[str, Any]:
        return {"value": len(hook_text), "extraction_method": "count", "source": "hook_text"}
