from __future__ import annotations

from typing import Any, Dict

from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer
from engines.hook_feature_analyzers.plugins._lexicon import INTERROGATIVE_OPENERS


class OpeningWordAnalyzer(HookFeatureAnalyzer):
    """Classifies the single opening word: number | interrogative | statement | empty."""

    @property
    def feature_name(self) -> str:
        return "opening_word_type"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, hook_text: str) -> Dict[str, Any]:
        words = hook_text.split()
        opening_word = words[0].lower() if words else ""

        if not opening_word:
            value = "empty"
        elif opening_word.isdigit():
            value = "number"
        elif opening_word in INTERROGATIVE_OPENERS:
            value = "interrogative"
        else:
            value = "statement"

        return {"value": value, "extraction_method": "rule_classification", "source": "hook_text"}
