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

    def build_monthly_plan(self, performance_data: str, current_plan: str) -> dict:
        prompt = f"""أنت مستشار استراتيجي لمنصة انستغرام متخصصة بالمحتوى النفسي.

بيانات الأداء الشهري:
{performance_data}

الخطة الحالية:
{current_plan}

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

    def diagnose_workflow_error(self, error_log: str) -> str:
        prompt = f"""أنت مهندس DevOps خبير. حلل هذا الخطأ واقترح الإصلاح:

{error_log}

أجب بالعربية أو الإنجليزية حسب محتوى الخطأ. قدّم:
1. سبب الخطأ
2. خطوات الإصلاح المقترحة
3. كيفية منع تكراره"""
        return self._call_with_fallback(prompt)

    def select_best_image(self, images: list, topic: str) -> dict | None:
        """Use the dedicated image-check key (never competes for text quota)."""
        if not images:
            return None

        image_check_key = self._engine.image_check_key
        if not image_check_key:
            # Fallback to rotation engine if no dedicated key
            image_check_key = None

        descriptions = "\n".join(
            f"{i+1}. {img.get('tags', '')} — {img.get('pageURL', '')}"
            for i, img in enumerate(images)
        )
        prompt = f"""اختر أفضل صورة خلفية لمنشور انستغرام عن: "{topic}"

الصور المتاحة:
{descriptions}

أخرج JSON فقط:
{{"selected_index": 1, "reason": "..."}}"""

        try:
            if image_check_key:
                # Use dedicated image key directly
                from google import genai
                client = genai.Client(api_key=image_check_key)
                resp = client.models.generate_content(
                    model=config.IMAGE_VETTING_MODEL, contents=prompt
                )
                raw = resp.text
            else:
                raw = self._call_with_fallback(prompt)
            result = self._extract_json(raw)
            idx = int(result.get("selected_index", 1)) - 1
            if 0 <= idx < len(images):
                return images[idx]
        except Exception:
            pass
        return images[0] if images else None
