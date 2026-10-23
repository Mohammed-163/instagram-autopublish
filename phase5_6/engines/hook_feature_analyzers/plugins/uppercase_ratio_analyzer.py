from __future__ import annotations

from typing import Any, Dict

from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer


class UppercaseRatioAnalyzer(HookFeatureAnalyzer):
    """Ratio of uppercase Latin letters to total Latin letters. 0 for
    hooks with no Latin letters at all (e.g. pure Arabic text has no
    upper/lowercase distinction)."""

    @property
    def feature_name(self) -> str:
        return "uppercase_ratio"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, hook_text: str) -> Dict[str, Any]:
        letters = [c for c in hook_text if c.isalpha() and c.isascii()]
        value = round(sum(1 for c in letters if c.isupper()) / len(letters), 4) if letters else 0.0
        return {"value": value, "extraction_method": "arithmetic", "source": "hook_text"}
