from __future__ import annotations

from typing import Any, Dict

from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer


class ParenthesesAnalyzer(HookFeatureAnalyzer):
    @property
    def feature_name(self) -> str:
        return "has_parentheses"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, hook_text: str) -> Dict[str, Any]:
        value = "(" in hook_text or ")" in hook_text
        return {"value": value, "extraction_method": "substring_search", "source": "hook_text"}
