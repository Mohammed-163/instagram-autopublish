from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class HookFeatureAnalyzer(ABC):
    """Interface every Hook Feature Analyzer plugin must implement.

    Analyzers are pure functions of `hook_text` (the isolated first line
    of a post) — no hard-coded success rules, no DB access, no LLM calls.
    They only extract an independent, named linguistic Feature.
    """

    @property
    @abstractmethod
    def feature_name(self) -> str:
        """Unique key this analyzer contributes to the features dict."""
        raise NotImplementedError

    @property
    @abstractmethod
    def version(self) -> str:
        """Semantic version of this analyzer's extraction logic. Bump this
        whenever the extraction logic changes so historical rows stay
        interpretable (they store the version that produced them)."""
        raise NotImplementedError

    @abstractmethod
    def analyze(self, hook_text: str) -> Dict[str, Any]:
        """Return a dict with at least:
            {"value": <extracted feature value>,
             "extraction_method": <short string, e.g. "regex" | "keyword_match" | "count">,
             "source": "hook_text"}
        Must be deterministic: same hook_text -> same output, always
        (required for Replay Support).
        """
        raise NotImplementedError
