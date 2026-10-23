from __future__ import annotations

import re
from typing import Any, Dict

from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "]+",
    flags=re.UNICODE,
)


class EmojiAnalyzer(HookFeatureAnalyzer):
    @property
    def feature_name(self) -> str:
        return "emoji_count"

    @property
    def version(self) -> str:
        return "1.0.0"

    def analyze(self, hook_text: str) -> Dict[str, Any]:
        count = sum(len(m) for m in _EMOJI_RE.findall(hook_text))
        return {"value": count, "extraction_method": "regex", "source": "hook_text"}
