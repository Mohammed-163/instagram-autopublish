from __future__ import annotations

from typing import Any, Dict

from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer


class OpeningPhraseAnalyzer(HookFeatureAnalyzer):
    """Extracts the opening phrase: the first 1-3 words of the hook, used
    downstream as a categorical Feature (independent of the single opening
    word)."""

    @property
    def feature_name(self) -> str:
        return "opening_phrase"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, hook_text: str) -> Dict[str, Any]:
        words = hook_text.split()
        phrase = " ".join(words[:3]).lower()
        return {"value": phrase, "extraction_method": "prefix_slice", "source": "hook_text"}
