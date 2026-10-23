from __future__ import annotations

import re
from typing import Any, Dict

from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer

_MULTI_SPACE_RE = re.compile(r"\s{2,}")


class WhitespacePatternAnalyzer(HookFeatureAnalyzer):
    """Counts irregular whitespace runs (2+ consecutive spaces) — a signal
    of manual formatting/emphasis in the hook."""

    @property
    def feature_name(self) -> str:
        return "irregular_whitespace_count"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, hook_text: str) -> Dict[str, Any]:
        return {
            "value": len(_MULTI_SPACE_RE.findall(hook_text)),
            "extraction_method": "regex",
            "source": "hook_text",
        }
