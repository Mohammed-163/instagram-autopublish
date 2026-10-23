from __future__ import annotations

import re
from typing import Any, Dict

from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer

_PERCENT_RE = re.compile(r"\d+\s*%|\bبالمئة\b|\bبالمائة\b|\bpercent\b")


class PercentageAnalyzer(HookFeatureAnalyzer):
    """Presence + normalized position of a percentage reference."""

    @property
    def feature_name(self) -> str:
        return "has_percentage"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, hook_text: str) -> Dict[str, Any]:
        match = _PERCENT_RE.search(hook_text)
        present = match is not None
        position = round(match.start() / len(hook_text), 4) if present and hook_text else None
        return {
            "value": {"present": present, "position": position},
            "extraction_method": "regex",
            "source": "hook_text",
        }
