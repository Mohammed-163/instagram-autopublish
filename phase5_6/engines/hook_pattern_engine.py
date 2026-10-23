"""
HookPatternDiscoveryEngine
==========================
Phase 4 Part 1 — item 5 (Hook Pattern Discovery) + item 3 (hook type
classification).

Responsibility:
- Listen to FeaturesExtracted (fired once a post's text/design features are
  available).
- Isolate the hook: the FIRST LINE of the post's final_text. Our content is
  image + text, never video/audio — the hook is purely textual.
- Extract hook-level features: word count, char count, presence of a number,
  presence of a question, presence of a comparison, presence of negation,
  presence of a warning word, presence of a curiosity word, hook length,
  punctuation density, and the opening-word type.
- Classify the hook into one of the fixed taxonomy types (Curiosity, Shock,
  Question, Comparison, Warning, Myth, Hidden Fact, Number, Before/After,
  Impossible, Contradiction, Psychology, History, Science, Body).
- Persist a HookPattern row (via HookService) and emit HookAnalyzed.

Design:
- Extends EngineBase — depends on PostService + HookService only, never on
  repositories.
- This engine does NOT decide whether a hook "worked" — that correlation
  with success is HookKnowledgeEngine's job (item 4), listening downstream
  on HookAnalyzed. This engine only classifies and extracts features.
- Classification uses a fixed, documented keyword taxonomy (required to
  even name a hook type) but never hard-codes which hook type "succeeds" —
  that is learned purely from data in HookKnowledgeEngine.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from core.events import FeaturesExtracted, HookAnalyzed
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)

HOOK_TYPES = (
    "curiosity", "shock", "question", "comparison", "warning", "myth",
    "hidden_fact", "number", "before_after", "impossible", "contradiction",
    "psychology", "history", "science", "body",
)

# Keyword signals used only to NAME/classify a hook (not to judge its
# success). Arabic + English since posts may be authored in either.
_KEYWORDS: Dict[str, List[str]] = {
    "warning": ["تحذير", "احذر", "خطر", "warning", "danger", "beware"],
    "myth": ["خرافة", "خطأ شائع", "myth", "misconception", "wrong belief"],
    "hidden_fact": ["حقيقة خفية", "لا يعرفها", "سر", "hidden fact", "secret", "few know"],
    "impossible": ["مستحيل", "لا يصدق", "impossible", "unbelievable"],
    "contradiction": ["عكس", "على عكس", "لكن", "contrary to", "actually", "in fact"],
    "before_after": ["قبل و بعد", "قبل وبعد", "before and after", "before/after"],
    "comparison": ["مقابل", "أفضل من", "vs", "versus", "compared to", "بدل"],
    "psychology": ["نفسي", "دماغك", "عقلك", "psychology", "brain", "mind"],
    "history": ["تاريخ", "قديماً", "history", "centuries ago", "ancient"],
    "science": ["علمياً", "دراسة", "علم", "science", "study shows", "research"],
    "body": ["جسمك", "جسدك", "body", "your body"],
    "shock": ["صدمة", "لن تصدق", "shocking", "shocked", "insane"],
}

_CURIOSITY_WORDS = ["فضول", "تخيل", "هل تعلم", "curious", "imagine", "did you know", "guess"]
_NEGATION_WORDS = ["لا", "ليس", "لن", "not", "never", "no ", "isn't", "doesn't"]


class HookPatternDiscoveryEngine(EngineBase):
    """Converts FeaturesExtracted -> HookAnalyzed. Purely statistical /
    rule-based feature extraction on the post's first line; no LLM calls."""

    ENGINE_NAME = "hook_pattern_discovery"

    def __init__(
        self,
        event_bus: Any,
        post_service: Any,
        hook_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.post_service = post_service
        self.hook_service = hook_service

    # ------------------------------------------------------------------ event handler
    def handle_features_extracted(self, event: FeaturesExtracted) -> None:
        try:
            post_id = event.post_id
            post = self.post_service.get_by_id(post_id)
            final_text = getattr(post, "final_text", None) if post is not None else None
            category = getattr(post, "category", None) if post is not None else None

            if not final_text:
                logger.info("[HookPatternDiscoveryEngine] Post %s has no text yet; skipping.", post_id)
                self.heartbeat("healthy")
                return

            hook_text = self.extract_hook_text(final_text)
            features = self.extract_hook_features(hook_text)
            hook_type = self.classify_hook_type(hook_text, features)

            self.hook_service.record_hook_pattern(
                post_id=post_id,
                hook_text=hook_text,
                hook_type=hook_type,
                features=features,
                category=category,
            )

            analyzed_event = HookAnalyzed(
                post_id=post_id,
                hook_text=hook_text,
                hook_type=hook_type,
                category=category,
                features=features,
            )
            self.event_bus.publish(analyzed_event)

            self.heartbeat("healthy")
            logger.info(
                "[HookPatternDiscoveryEngine] post=%s hook_type=%s category=%s",
                post_id, hook_type, category,
            )

        except Exception as e:
            logger.exception("[HookPatternDiscoveryEngine] Error analyzing hook: %s", e)
            self.heartbeat("error", error=str(e))

    # ------------------------------------------------------------------ hook isolation
    @staticmethod
    def extract_hook_text(final_text: str) -> str:
        """The hook is the FIRST LINE only (displayed in a different color,
        its job is to stop the scroll)."""
        first_line = final_text.strip().splitlines()[0] if final_text.strip() else ""
        return first_line.strip()

    # ------------------------------------------------------------------ feature extraction
    def extract_hook_features(self, hook_text: str) -> Dict[str, Any]:
        words = hook_text.split()
        punctuation = re.findall(r"[!?؟.,،؛:]", hook_text)
        opening_word = words[0].lower() if words else ""

        return {
            "word_count": len(words),
            "char_count": len(hook_text),
            "has_number": bool(re.search(r"\d", hook_text)),
            "has_question": "؟" in hook_text or "?" in hook_text,
            "has_comparison": self._contains_any(hook_text, _KEYWORDS["comparison"]),
            "has_negation": self._contains_any(hook_text, _NEGATION_WORDS),
            "has_warning": self._contains_any(hook_text, _KEYWORDS["warning"]),
            "has_curiosity_word": self._contains_any(hook_text, _CURIOSITY_WORDS),
            "hook_length": len(hook_text),
            "punctuation_density": round(len(punctuation) / max(1, len(hook_text)), 4),
            "opening_type": self._opening_type(opening_word),
        }

    # ------------------------------------------------------------------ classification
    def classify_hook_type(self, hook_text: str, features: Dict[str, Any]) -> str:
        """Classify into the fixed taxonomy. Checked in a fixed priority
        order so classification is deterministic and reproducible."""
        for hook_type in (
            "warning", "myth", "hidden_fact", "impossible", "contradiction",
            "before_after", "comparison", "psychology", "history", "science", "body", "shock",
        ):
            if self._contains_any(hook_text, _KEYWORDS[hook_type]):
                return hook_type

        if features.get("has_question"):
            return "question"
        if features.get("has_number"):
            return "number"
        if features.get("has_curiosity_word"):
            return "curiosity"

        return "curiosity"  # default fallback: stop-the-scroll intent

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _contains_any(text: str, keywords: List[str]) -> bool:
        lowered = text.lower()
        return any(kw.lower() in lowered for kw in keywords)

    @staticmethod
    def _opening_type(opening_word: str) -> str:
        if not opening_word:
            return "empty"
        if opening_word.isdigit():
            return "number"
        if opening_word in ("هل", "did", "do", "why", "لماذا", "كيف", "how", "what", "ماذا"):
            return "interrogative"
        return "statement"
