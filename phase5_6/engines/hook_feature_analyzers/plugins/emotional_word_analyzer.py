from __future__ import annotations

from typing import Any, Dict

from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer
from engines.hook_feature_analyzers.plugins._lexicon import EMOTIONAL_WORDS
from engines.hook_feature_analyzers.plugins._keyword_utils import find_first_position


class EmotionalWordAnalyzer(HookFeatureAnalyzer):
    @property
    def feature_name(self) -> str:
        return "has_emotional_word"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, hook_text: str) -> Dict[str, Any]:
        present, position = find_first_position(hook_text, EMOTIONAL_WORDS)
        return {
            "value": {"present": present, "position": position},
            "extraction_method": "keyword_match",
            "source": "hook_text",
        }
