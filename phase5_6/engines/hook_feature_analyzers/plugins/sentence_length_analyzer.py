from __future__ import annotations

import re
from typing import Any, Dict

from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer

_SENTENCE_SPLIT_RE = re.compile(r"[.!?؟]+")


class SentenceLengthAnalyzer(HookFeatureAnalyzer):
    """Average word count per sentence within the hook (a hook is usually
    one sentence, but may contain more than one clause)."""

    @property
    def feature_name(self) -> str:
        return "sentence_length"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, hook_text: str) -> Dict[str, Any]:
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(hook_text) if s.strip()]
        if not sentences:
            value = 0.0
        else:
            value = round(sum(len(s.split()) for s in sentences) / len(sentences), 4)
        return {"value": value, "extraction_method": "sentence_split", "source": "hook_text"}
