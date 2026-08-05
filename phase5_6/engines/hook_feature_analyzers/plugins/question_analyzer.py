from __future__ import annotations

from typing import Any, Dict

from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer

_MARKS = ("؟", "?")


class QuestionAnalyzer(HookFeatureAnalyzer):
    """Presence + normalized position of a question mark (Arabic or Latin)."""

    @property
    def feature_name(self) -> str:
        return "has_question"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, hook_text: str) -> Dict[str, Any]:
        position = None
        present = False
        for mark in _MARKS:
            idx = hook_text.find(mark)
            if idx != -1:
                present = True
                position = idx if position is None else min(position, idx)
        norm_position = round(position / len(hook_text), 4) if present and hook_text else None
        return {
            "value": {"present": present, "position": norm_position},
            "extraction_method": "substring_search",
            "source": "hook_text",
        }
