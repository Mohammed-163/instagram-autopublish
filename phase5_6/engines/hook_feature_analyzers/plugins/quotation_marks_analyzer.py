from __future__ import annotations

from typing import Any, Dict

from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer

_QUOTE_CHARS = ('"', "'", "\u201c", "\u201d", "\u00ab", "\u00bb")


class QuotationMarksAnalyzer(HookFeatureAnalyzer):
    @property
    def feature_name(self) -> str:
        return "has_quotation_marks"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, hook_text: str) -> Dict[str, Any]:
        value = any(ch in hook_text for ch in _QUOTE_CHARS)
        return {"value": value, "extraction_method": "substring_search", "source": "hook_text"}
