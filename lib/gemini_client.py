"""
Gemini API wrapper with 3-key rotation (free-tier quota fallback).
Handles: daily post content generation (with self-verification),
monthly plan building, and error diagnosis for the auto-fix-PR flow.
"""
import json
import re
import time

import google.generativeai as genai

from . import config


class AllKeysExhaustedError(Exception):
    pass


class GeminiClient:
    def __init__(self, api_keys: list, image_check_key: str = ""):
        self.api_keys = [k for k in api_keys if k]
        if not self.api_keys:
            raise ValueError("GeminiClient requires at least one API key")
        # Reserved key used ONLY for image vetting (see select_best_image),
        # so it never competes for quota with the daily text-generation keys.
        self.image_check_key = image_check_key or ""

    def _call_with_fallback(self, prompt: str) -> str:
        last_error = None
        for i, key in enumerate(self.api_keys):
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:
                print(f"🔴 [تفاصيل الخطأ الحقيقي للمفتاح {i + 1}]: {e}")
                
                error_str = str(e).lower()
                if "quota" in error_str or "429" in error_str or "resource_exhausted" in error_str:
                    print(f"⚠️ Gemini key #{i + 1} quota exhausted or rate limited (429).")
                    print("⏳ ننتظر 20 ثانية لتبريد عداد جوجل قبل تجربة المفتاح التالي...")
                    time.sleep(20)
                    last_error = e
                    continue
                raise
        raise AllKeysExhaustedError(f"All {len(self.api_keys)} Gemini keys exhausted: {last_error}")

    @staticmethod
    def _extract_json(text: str) -> dict:
        cleaned = re.sub(r"^```json\s*|```\s*$", "", text.strip(), flags=re.MULTILINE)
        return json.loads(cleaned)

    def _word_count_ok(self, text: str, field: str) -> bool:
        lo, hi = config.WORD_LIMITS[field]
        count = len(text.strip().split())
        return lo <= count <= hi

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
                continue

            if data.get("confidence_check") != "verified":
                continue

            fields_ok = all(
                self._word_count_ok(data.get(field, ""), field)
                for field in ("hook_line", "fact_line", "cta_line")
            )
            if fields_ok:
                return data

        raise ValueError("Gemini failed to produce a verified, in-budget post after retries")

    def build_monthly_plan(self, insights_json: dict, competitor_json: dict, current_date_str: str) -> list:
        prompt = f"""أنت مخطط محتوى استراتيجي لحساب انستغرام متخصص بـ"حقائق نفسية سريعة".

التاريخ الحالي الفعلي لليوم هو: {current_date_str}

بيانات أداء فعلية لكل منشور نُشر سابقاً، مع الموضوع (topic_slug) والنص الفعلي
(hook_line/fact_line) ومقاييس التفاعل الحقيقية (reach/saved/shares/likes/comments) (JSON):
{json.dumps(insights_json, ensure_ascii=False)}

تحليل المنافسين (JSON):
{json.dumps(competitor_json, ensure_ascii=False)}

المطلوب: خطة نشر لـ30 يوماً قادمة.
قبل بناء الخطة، حلل بيانات الأداء أعلاه لتحدد:
- أي topic_slug/زاوية حقق أعلى معدل حفظ (saved/reach) ومشاركة (shares) — هذه المواضيع
  يجب تفضيل مواضيع مشابهة لها أو تطويرها بزوايا جديدة
- أي مواضيع كان أداؤها ضعيفاً بشكل واضح — تجنّب تكرار نفس الزاوية فيها
لا تفترض شيئاً إذا كانت بيانات الأداء فارغة أو قليلة (حساب جديد)؛ في هذه الحالة اعتمد فقط
على تحليل المنافسين وحسّك الاستراتيجي العام.

تنبيه حاسم وصارم: يجب أن تبدأ تواريخ الأيام في الخطة من تاريخ اليوم ({current_date_str}) صعوداً وتتقدم يوماً بعد يوم بالتسلسل الصحيح لـ30 يوماً قادمة. لا تقم أبداً باختراع أو استخدام تواريخ قديمة أو من سنوات سابقة.

لكل يوم حدد:
- عدد المنشورات (1 إلى 3) بناءً على الأداء الفعلي (لا تفترض رقماً ثابتاً)
- نوع كل منشور ووقت مقترح (تنويع بين الصباح والمساء حسب أفضل أوقات التفاعل بالبيانات)
- كلمات بحث Pixabay لكل منشور (وصف بصري مجرد: ألوان/تدرجات، ليس حرفياً)
- وزّن الأولوية حسب معدل الحفظ (saved/reach) والمشاركة (shares) أكثر من الإعجابات، وبناءً
  على تحليل الأداء الفعلي لكل موضوع كما هو موضح أعلاه

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

    def select_best_image(self, image_paths: list, topic_summary: str) -> int:
        """Sends all candidate background images to Gemini in one call and
        asks it to (a) reject any that are religiously/culturally
        inappropriate (nudity, suggestive content, alcohol/drugs, or
        anything else not permissible in Islam) and (b) among the remaining
        ones, pick whichever best visually matches the post's topic.

        Uses ONLY self.image_check_key — a separate, reserved key — never
        the rotation keys used for text generation, so image moderation
        never competes with daily content generation for quota.

        Returns the index (0-based) of the best candidate, or -1 if none of
        the candidates are acceptable / nothing could be evaluated.
        """
        if not self.image_check_key:
            raise ValueError("select_best_image requires GEMINI_API_KEY_IMAGE_CHECK to be set")
        if not image_paths:
            return -1

        from PIL import Image as PILImage

        images = []
        for path in image_paths:
            try:
                images.append(PILImage.open(path).convert("RGB"))
            except Exception as e:
                print(f"⚠️ Could not open candidate image {path} for vetting: {e}")

        if not images:
            return -1

        prompt = f"""أنت تراجع صور خلفية مرشحة لمنشور انستغرام عن الموضوع التالي:
"{topic_summary}"

لديك {len(images)} صورة مرقّمة بالترتيب من 0 إلى {len(images) - 1} (بنفس ترتيب ظهورها هنا).

الخطوة 1 — الفحص الشرعي/الأخلاقي (إلزامي، ارفض أي صورة فيها):
- عري أو ملابس كاشفة أو محتوى مثير
- خمور أو مخدرات أو أي مادة محرّمة ظاهرة
- أي محتوى آخر محرّم شرعاً (رموز دينية غير إسلامية بشكل صريح، عنف، إلخ)

الخطوة 2 — من بين الصور التي اجتازت الفحص الشرعي فقط، اختر الأنسب بصرياً
لموضوع المنشور (ألوان، أجواء، تناسب مع المحتوى).

أخرج الناتج بصيغة JSON فقط بدون أي نص إضافي، بالضبط بهذا الشكل:
{{
  "rejected_indices": [ارقام الصور المرفوضة شرعياً, قد تكون فارغة []],
  "selected_index": الرقم الأنسب من الصور المقبولة، أو -1 اذا كل الصور مرفوضة أو غير مناسبة إطلاقاً
}}"""

        contents = [prompt] + images
        try:
            genai.configure(api_key=self.image_check_key)
            model = genai.GenerativeModel(config.IMAGE_VETTING_MODEL_NAME)
            response = model.generate_content(contents)
            data = self._extract_json(response.text)
            selected = int(data.get("selected_index", -1))
            if 0 <= selected < len(images):
                return selected
            return -1
        except Exception as e:
            print(f"🔴 Image vetting call failed: {e}")
            return -1

    def diagnose_error(self, error_message: str, code_snippet: str) -> str:
        prompt = f"""حلل خطأ البرمجة التالي واقترح إصلاحاً دقيقاً.

رسالة الخطأ:
{error_message}

جزء الكود المتعلق بالخطأ:
{code_snippet}

أعطني فقط الكود المُصحح الكامل لهذا الجزء (بدون شرح إضافي)، بحيث يمكن استخدامه مباشرة كبديل للكود الأصلي."""
        return self._call_with_fallback(prompt)
