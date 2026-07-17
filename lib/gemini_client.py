"""
Gemini API wrapper with 3-key rotation (free-tier quota fallback).
Handles: daily post content generation (with self-verification),
monthly plan building, and error diagnosis for the auto-fix-PR flow.
"""
import json
import re

import google.generativeai as genai

from . import config


class AllKeysExhaustedError(Exception):
    pass


class GeminiClient:
    def __init__(self, api_keys: list):
        self.api_keys = [k for k in api_keys if k]
        if not self.api_keys:
            raise ValueError("GeminiClient requires at least one API key")

    def _call_with_fallback(self, prompt: str) -> str:
        last_error = None
        for i, key in enumerate(self.api_keys):
            try:
                genai.configure(api_key=key)
                # تم التعديل هنا لطلب إصدار 1.5 مباشرة لتجاوز حظر الحصة المجانية
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:  # google.api_core exceptions vary by version
                # السطر الجديد لكشف الخطأ الحقيقي
                print(f"🔴 [تفاصيل الخطأ الحقيقي للمفتاح {i + 1}]: {e}")
                
                error_str = str(e).lower()
                if "quota" in error_str or "429" in error_str or "resource_exhausted" in error_str:
                    print(f"⚠️ Gemini key #{i + 1} quota exhausted, trying next key")
                    last_error = e
                    continue
                raise  # any other error is not a quota issue — surface immediately
        raise AllKeysExhaustedError(f"All {len(self.api_keys)} Gemini keys exhausted: {last_error}")

    @staticmethod
    def _extract_json(text: str) -> dict:
        # Strip markdown code fences if the model added them despite instructions
        cleaned = re.sub(r"^```json\s*|```\s*$", "", text.strip(), flags=re.MULTILINE)
        return json.loads(cleaned)

    def _word_count_ok(self, text: str, field: str) -> bool:
        lo, hi = config.WORD_LIMITS[field]
        count = len(text.strip().split())
        return lo <= count <= hi

    def generate_post_content(self, recent_topics: list, post_type: str = "quick_psychological_fact") -> dict:
        """Generates one post's content. Retries once with a different angle
        if confidence_check fails or word budgets are violated."""
        avoid_list = ", ".join(recent_topics) if recent_topics else "(لا يوجد سجل سابق بعد)"

        prompt = f"""أنت كاتب محتوى متخصص بـ"حقائق نفسية سريعة" لمنشورات انستغرام قصيرة (فئة: {post_type}).

مواضيع نُشرت مسبقاً ويجب تجنب تكرارها: {avoid_list}

المطلوب: حقيقة نفسية واحدة، مثبتة علمياً وموثوقة فعلاً (وليست خرافة شائعة أو معلومة غير مؤكدة).
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
  "caption_arabic": "وصف أطول قليلاً (2-3 جمل) بنفس نبرة الصوت لوضعه تحت المنشور",
  "hashtags": ["#...", "#...", "#..."],
  "pixabay_query": "كلمات إنجليزية بحث بصري مجرد (ألوان/تدرجات) تناسب الموضوع",
  "confidence_check": "verified"
}}
إذا لم تكن واثقاً من صحة الحقيقة علمياً، اجعل confidence_check تساوي "unverified" بدلاً من اختلاق معلومة."""

        for attempt in range(config.GEMINI_MAX_TOPIC_RETRIES + 1):
            raw = self._call_with_fallback(prompt)
            try:
                data = self._extract_json(raw)
            except (json.JSONDecodeError, ValueError):
                continue  # malformed JSON, retry

            if data.get("confidence_check") != "verified":
                continue

            fields_ok = all(
                self._word_count_ok(data.get(field, ""), field)
                for field in ("hook_line", "fact_line", "cta_line")
            )
            if fields_ok:
                return data
            # otherwise fall through to retry

        raise ValueError("Gemini failed to produce a verified, in-budget post after retries")

    def build_monthly_plan(self, insights_json: dict, competitor_json: dict) -> list:
        """Returns a list of daily plan rows matching CURRENT_PLAN_HEADERS order."""
        prompt = f"""أنت مخطط محتوى استراتيجي لحساب انستغرام متخصص بـ"حقائق نفسية سريعة".

بيانات أداء آخر 30 يوم (JSON):
{json.dumps(insights_json, ensure_ascii=False)}

تحليل المنافسين (JSON):
{json.dumps(competitor_json, ensure_ascii=False)}

المطلوب: خطة نشر لـ30 يوماً قادمة. لكل يوم حدد:
- عدد المنشورات (1 إلى 3) بناءً على الأداء الفعلي (لا تفترض رقماً ثابتاً)
- نوع كل منشور ووقت مقترح (تنويع بين الصباح والمساء حسب أفضل أوقات التفاعل بالبيانات)
- كلمات بحث Pixabay لكل منشور (وصف بصري مجرد: ألوان/تدرجات، ليس حرفياً)
- وزّن الأولوية حسب معدل الحفظ (saved/reach) والمشاركة (shares) أكثر من الإعجابات

أخرج الناتج بصيغة JSON فقط، مصفوفة من 30 عنصراً، بالضبط بهذا الشكل لكل يوم:
{{
  "date": "YYYY-MM-DD",
  "post_count": 1,
  "posts": [
    {{"type": "quick_psychological_fact", "time": "HH:MM", "bg_keywords": "..."}}
  ]
}}"""
        raw = self._call_with_fallback(prompt)
        days = self._extract_json(raw)

        rows = []
        for day in days:
            row = [day["date"], day["post_count"]]
            posts = day.get("posts", [])
            for i in range(3):
                if i < len(posts):
                    p = posts[i]
                    row += [p.get("type", ""), p.get("time", ""), p.get("bg_keywords", ""), ""]
                else:
                    row += ["", "", "", ""]
            rows.append(row)
        return rows

    def diagnose_error(self, error_message: str, code_snippet: str) -> str:
        """Returns a suggested fix (as a unified diff or corrected code block)."""
        prompt = f"""حلل خطأ البرمجة التالي واقترح إصلاحاً دقيقاً.

رسالة الخطأ:
{error_message}

جزء الكود المتعلق بالخطأ:
{code_snippet}

أعطني فقط الكود المُصحح الكامل لهذا الجزء (بدون شرح إضافي)، بحيث يمكن استخدامه مباشرة كبديل للكود الأصلي."""
        return self._call_with_fallback(prompt)
