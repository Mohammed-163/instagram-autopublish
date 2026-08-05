from __future__ import annotations

import re
from typing import Any, Dict

from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer

_NUMBER_RE = re.compile(r"\d+")


class NumberAnalyzer(HookFeatureAnalyzer):
    """Presence + normalized position (0..1, or None if absent) of the
    first digit sequence in the hook."""

    @property
    def feature_name(self) -> str:
        return "has_number"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, hook_text: str) -> Dict[str, Any]:
        match = _NUMBER_RE.search(hook_text)
        present = match is not None
        position = round(match.start() / len(hook_text), 4) if present and hook_text else None
        return {
            "value": {"present": present, "position": position},
            "extraction_method": "regex",
            "source": "hook_text",
        }
