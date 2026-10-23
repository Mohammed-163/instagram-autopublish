"""Shared keyword lists for keyword-matching analyzers. Not a plugin itself
(no HookFeatureAnalyzer subclass lives here) — the plugin loader skips it
automatically. Arabic + English, matching the existing taxonomy used by
HookPatternDiscoveryEngine (engines/hook_pattern_engine.py) so both engines
agree on vocabulary.

These lists only ever describe WHICH words are present (a Feature) — they
never encode which combination "succeeds". That is learned later, purely
from data, by HookKnowledgeEngine / the future Opportunity Discovery layer.
"""

CURIOSITY_WORDS = ["فضول", "تخيل", "هل تعلم", "curious", "imagine", "did you know", "guess"]
NEGATION_WORDS = ["لا", "ليس", "لن", "not", "never", "no ", "isn't", "doesn't"]
WARNING_WORDS = ["تحذير", "احذر", "خطر", "warning", "danger", "beware"]
COMPARISON_WORDS = ["مقابل", "أفضل من", "vs", "versus", "compared to", "بدل"]
PROMISE_WORDS = ["ستتعلم", "ستكتشف", "سوف", "you will", "you'll", "guaranteed", "promise", "ستحصل"]
TIME_REFERENCE_WORDS = [
    "اليوم", "الآن", "قديماً", "قريباً", "دقائق", "ثواني",
    "today", "now", "seconds", "minutes", "years ago", "recently",
]
EMOTIONAL_WORDS = [
    "صدمة", "خوف", "حب", "غضب", "فرح", "حزن",
    "shocking", "afraid", "love", "angry", "happy", "sad", "amazing", "terrifying",
]
SCIENTIFIC_WORDS = ["علمياً", "دراسة", "علم", "science", "study shows", "research", "scientists"]
HISTORICAL_WORDS = ["تاريخ", "قديماً", "history", "centuries ago", "ancient", "قرون"]
PSYCHOLOGY_WORDS = ["نفسي", "دماغك", "عقلك", "psychology", "brain", "mind", "subconscious"]
HUMAN_BODY_WORDS = ["جسمك", "جسدك", "قلبك", "دماغك", "body", "your body", "heart", "brain"]
INTERROGATIVE_OPENERS = ("هل", "did", "do", "why", "لماذا", "كيف", "how", "what", "ماذا", "when", "متى")
