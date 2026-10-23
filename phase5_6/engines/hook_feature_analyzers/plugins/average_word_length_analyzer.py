from __future__ import annotations

from typing import Any, Dict

from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer


class AverageWordLengthAnalyzer(HookFeatureAnalyzer):
    @property
    def feature_name(self) -> str:
        return "average_word_length"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, hook_text: str) -> Dict[str, Any]:
        words = hook_text.split()
        value = round(sum(len(w) for w in words) / len(words), 4) if words else 0.0
        return {"value": value, "extraction_method": "arithmetic", "source": "hook_text"}
