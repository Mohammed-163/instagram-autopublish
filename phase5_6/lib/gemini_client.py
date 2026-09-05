"""
Gemini API wrapper backed by the new google-genai SDK.

Uses GeminiRotationEngine (operational/gemini_rotation.py) for
production-ready 2-level key×model rotation with health tracking,
cooldown management, and structured logging.

Legacy API (google.generativeai / genai.configure) is no longer used.
"""
from __future__ import annotations

import json
import re
import sys
import os

# Ensure project root is on path so operational module is findable
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from operational.gemini_rotation import GeminiRotationEngine, AllCombinationsExhaustedError, FREE_MODELS
from . import config


class AllKeysExhaustedError(Exception):
    """Raised when every key×model combination is exhausted."""


class ImageVettingError(Exception):
    """Raised when the Gemini Vision image-vetting call fails (API error, bad key,
    unreadable file, or unparseable response).  Distinct from a *rejection* result
    (selected_index == -1), which is a normal outcome and returns None instead."""


class GeminiClient:
    """
    Drop-in replacement backed by GeminiRotationEngine.

    Rotation order (free-tier only):
        Key 1 → gemini-3.1-flash-lite → gemini-3.5-flash-lite → gemini-3.5-flash → gemini-3.6-flash
        Key 2 → (same model order)
        Key 3 → (same model order)
    """

    def __init__(self, api_keys: list, image_check_key: str = ""):
        self._engine = GeminiRotationEngine(
            api_keys=api_keys,
            models=FREE_MODELS,
            image_check_key=image_check_key,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _call_with_fallback(self, prompt: str) -> str:
        """Try all key×model combos; raise AllKeysExhaustedError on total failure."""
        try:
            return self._engine.generate(prompt)
        except AllCombinationsExhaustedError as exc:
            raise AllKeysExhaustedError(str(exc)) from exc

    @staticmethod
    def _extract_json(text: str) -> dict:
        cleaned = re.sub(r"^```json\s*|```\s*$", "", text.strip(), flags=re.MULTILINE)
        return json.loads(cleaned)

    def _word_count_ok(self, text: str, field: str) -> bool:
        lo, hi = config.WORD_LIMITS[field]
        count = len(text.strip().split())
        return lo <= count <= hi

    # ------------------------------------------------------------------
    # Content generation
    # ------------------------------------------------------------------
    def generate_post_content(self, recent_topics: list, post_type: str = "quick_psychological_fact") -> dict:
        avoid_list = ", ".join(recent_topics) if recent_topics else "(لا يوجد سجل سابق بعد)"

        prompt = f"""أنت كاتب محتوى متخصص بـ"حقائق نفسية سريعة" لمنشورات انستغرام قصيرة (فئة: {post_type}).

مواضيع نُشرت مسبقاً ويجب تجنب تكرارها: {avoid_list}

الملطوب: حقيقة نفسية واحدة، مثبتة علمياً وموثوقة فعلاً (وليست خرافة شائعة أو معلومة غير مؤكدة).
إذا لم تكن متأكداً 100% من صحة معلومة معينة علمياً، اختر موضوعاً نفسياً آخر تكون واثقاً منه بدلاً منها.
لا تقدم أي تشخيص أو نصيحة طبية/علاجية مباشرة.

التزم بميزانية الكلمات التالية بدقة:
- hook_line: 4-6 كلمات (جملة تلفت الانتباه، سؤال أو صدمة قصيرة)
- fact_line: 8-12 كلمة (الحقيقة نفسها بوضوح تام)
- cta_line: 3-5 كلمات (دعوة للحفظ أو المشاركة)

أخرج الناتج بصيغة JSON فقط، بدون أي نص أو تنسيق إضافي قبله أو بعده، بالضبط بهذا الشكل:
{{
  "topic_slug": "معرف قصير بالإنجليزية بدون مسافات",
  "hook_line": "...",
  "fact_line": "...",
  "cta_line": "...",
  "pixabay_query": "2-4 english keywords describing a calm/abstract background image that fits the topic"
}}"""

        for attempt in range(3):
            raw = self._call_with_fallback(prompt)
            try:
                data = self._extract_json(raw)
                required = ["topic_slug", "hook_line", "fact_line", "cta_line", "pixabay_query"]
                if not all(k in data for k in required):
                    continue
                return data
            except (json.JSONDecodeError, ValueError):
                continue
        raise ValueError("Failed to generate valid post content after 3 attempts")

    def generate_caption_and_hashtags(self, hook_line: str, fact_line: str, cta_line: str) -> dict:
        prompt = f"""أنت كاتب محتوى بارع لمنشورات انستغرام عربية.

المعطيات:
- hook_line: {hook_line}
- fact_line: {fact_line}
- cta_line: {cta_line}

المطلوب: اكتب caption عربية كاملة + 20-25 هاشتاق مناسب.

أخرج JSON فقط:
{{
  "caption_arabic": "...",
  "hashtags": "#tag1 #tag2 ..."
}}"""
        raw = self._call_with_fallback(prompt)
        return self._extract_json(raw)

    def build_monthly_plan(self, performance_data: str, competitor_data: str, date_str: str) -> dict:
        prompt = f"""أنت مستشار استراتيجي لمنصة انستغرام متخصصة بالمحتوى النفسي.

بيانات الأداء الشهري:
{performance_data}

بيانات المنافسين:
{competitor_data}

الشهر المستهدف:
{date_str}

بناءً على البيانات أعلاه، اقترح خطة شهر قادم محسّنة.
أخرج JSON فقط:
{{
  "strategy_summary": "...",
  "recommended_topics": ["topic1", "topic2"],
  "post_frequency": "daily",
  "focus_areas": ["area1", "area2"],
  "avoid_topics": ["topic_to_avoid"]
}}"""
        raw = self._call_with_fallback(prompt)
        return self._extract_json(raw)

    def build_weekly_plan(self, weekly_summary: dict) -> dict:
        prompt = f"""أنت مستشار استراتيجي لمنصة انستغرام متخصصة بالمحتوى النفسي.
خلاصة أداء الأسبوع الماضي:
{weekly_summary}

أنشئ خطة محتوى للأسبوع القادم. إذا كانت الخلاصة فارغة فأنشئ خطة ابتدائية معقولة.
أخرج JSON فقط:
{{
  "strategy_summary": "...",
  "recommended_topics": ["topic1", "topic2"],
  "post_frequency": "daily",
  "focus_areas": ["area1", "area2"],
  "avoid_topics": ["topic_to_avoid"]
}}"""
        required = [
            "strategy_summary",
            "recommended_topics",
            "post_frequency",
            "focus_areas",
            "avoid_topics",
        ]
        for attempt in range(3):
            raw = self._call_with_fallback(prompt)
            try:
                data = self._extract_json(raw)
                if not all(key in data for key in required):
                    continue
                return data
            except (json.JSONDecodeError, ValueError):
                continue
        raise ValueError("Failed to generate valid weekly plan after 3 attempts")

    def diagnose_workflow_error(self, error_log: str) -> str:
        prompt = f"""أنت مهندس DevOps خبير. حلل هذا الخطأ واقترح الإصلاح:

{error_log}

أجب بالعربية أو الإنجليزية حسب محتوى الخطأ. قدّم:
1. سبب الخطأ
2. خطوات الإصلاح المقترحة
3. كيفية منع تكراره"""
        return self._call_with_fallback(prompt)

    def select_best_image(self, image_paths: list, topic: str) -> str | None:
        """Vet candidate background images via Gemini Vision and return the path
        of the best acceptable one, or None if no candidate passes vetting.

        Args:
            image_paths: Local file paths returned by PixabayClient.download_candidates().
            topic: Human-readable topic summary used for relevance and compliance scoring.

        Returns:
            The file path of the selected image, or None if Gemini rejects every
            candidate (selected_index == -1) or the list is empty.

        Raises:
            ImageVettingError: If the Gemini Vision API call itself fails, or a
                               candidate image file cannot be read.  Callers must NOT
                               silently fall back to the first image on this error.
        """
        if not image_paths:
            return None

        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError as exc:
            raise ImageVettingError(
                "google-genai is required for image vetting: pip install google-genai"
            ) from exc

        # Prefer the dedicated image-check key so vetting never competes with
        # text-generation quota.  Fall back to the first available rotation key.
        api_key = self._engine.image_check_key
        if not api_key:
            available = [k for k in self._engine.api_keys if k]
            if not available:
                raise ImageVettingError(
                    "No Gemini API key available for image vetting "
                    "(set GEMINI_API_KEY_IMAGE_CHECK or at least one GEMINI_API_KEY_N)."
                )
            api_key = available[0]

        # Build a multimodal content list: one image-bytes part + label per candidate,
        # then a single text instruction.
        # The previous implementation called img.get('tags', ...) on string paths —
        # that raised AttributeError which was silently swallowed by a bare
        # 'except Exception: pass', causing the first image to always be returned
        # without any real vetting.  Here we send the actual JPEG bytes so Gemini
        # can inspect the images directly.
        parts = []
        for i, path in enumerate(image_paths):
            try:
                with open(path, "rb") as fh:
                    image_bytes = fh.read()
            except OSError as exc:
                raise ImageVettingError(
                    f"Cannot read candidate image {path!r}: {exc}"
                ) from exc
            parts.append(genai_types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
            parts.append(genai_types.Part.from_text(text=f"[صورة {i + 1}]"))

        n = len(image_paths)
        parts.append(genai_types.Part.from_text(text=(
            f'من الصور أعلاه ({n} صورة مُرقَّمة من 1 إلى {n})، '
            f'اختر أفضل صورة خلفية لمنشور انستغرام عن: "{topic}".\n'
            f'شروط القبول: الصورة لائقة، خالية من محتوى غير لائق (كحول/عري/عنف)، '
            f'ومناسبة بصرياً للموضوع.\n'
            f'إذا لم تجد أي صورة مقبولة اختر selected_index: -1.\n'
            f'أخرج JSON فقط:\n'
            f'{{"selected_index": <عدد صحيح 1-{n} أو -1>, "reason": "..."}}'
        )))

        # Call Gemini Vision (bypasses rotation engine — intentional: image vetting
        # must not consume text-generation quota).
        try:
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model=config.IMAGE_VETTING_MODEL,
                contents=parts,
            )
            raw = resp.text
            if raw is None:
                raise ImageVettingError(
                    "Gemini returned an empty response during image vetting "
                    f"(model={config.IMAGE_VETTING_MODEL})."
                )
        except ImageVettingError:
            raise
        except Exception as exc:
            raise ImageVettingError(
                f"Gemini Vision API call failed during image vetting: {exc}"
            ) from exc

        # Parse the 1-based index returned by Gemini.
        try:
            result = self._extract_json(raw)
            raw_idx = int(result.get("selected_index", -1))
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise ImageVettingError(
                f"Cannot parse Gemini image-selection response: {raw!r}"
            ) from exc

        if raw_idx == -1:
            # Gemini explicitly rejected every candidate.
            return None

        idx = raw_idx - 1  # convert 1-based (Gemini) → 0-based (Python)
        if 0 <= idx < len(image_paths):
            return image_paths[idx]

        # Gemini returned an out-of-range index — treat as rejection.
        return None
