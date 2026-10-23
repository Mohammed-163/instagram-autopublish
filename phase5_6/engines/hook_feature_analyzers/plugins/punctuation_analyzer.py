from __future__ import annotations

import re
from typing import Any, Dict

from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer

_PUNCTUATION_RE = re.compile(r"[!?؟.,،؛:]")


class PunctuationAnalyzer(HookFeatureAnalyzer):
    """Raw punctuation count + density (count / char_count)."""

    @property
    def feature_name(self) -> str:
        return "punctuation_density"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, hook_text: str) -> Dict[str, Any]:
        matches = _PUNCTUATION_RE.findall(hook_text)
        density = round(len(matches) / max(1, len(hook_text)), 4)
        return {
            "value": {"count": len(matches), "density": density},
            "extraction_method": "regex",
            "source": "hook_text",
        }
