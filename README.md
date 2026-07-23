# Instagram Auto-Publish System

نظام آلي كامل ينشر 1-3 منشورات يومياً على انستغرام (Reels نصية بالعربي، 6 ثواني،
فئة "حقائق نفسية سريعة")، مبني بالكامل على أدوات مجانية.

## الحالة الحالية

⚠️ **النظام بمرحلة الاختبار**. كل جدولة (`cron`) بملفات `.github/workflows/`
معطّلة مؤقتاً — فقط `test_validation.yml` مفعّل (تشغيل يدوي). لا تفعّل باقي
الجدولة إلا بعد نجاح اختبار Drive→Instagram.

## الإعداد

1. أضف الأسرار المطلوبة عبر Settings → Secrets and variables → Actions بالريبو
   (شوف القائمة الكاملة بـ`SETUP_REPORT.md`)
2. شغّل workflow `Test - Drive to Instagram Validation` يدوياً من تبويبة Actions
3. راجع نتيجة التشغيل — عند النجاح، فعّل باقي الجدولة بإزالة `#` من أسطر الـcron

## البنية

```
lib/         مكتبات مشتركة (Sheets, Drive, Gemini, Instagram, Pixabay, Video, Errors)
scripts/     السكربتات القابلة للتشغيل (توليد، نشر، تنظيف، مهمة شهرية، نسخ احتياطي)
.github/workflows/   جدولة GitHub Actions
assets/fonts/        خط Tajawal ExtraBold (مرخّص مجاناً - Google Fonts / OFL)
```

## البنية المطلوبة بـGoogle Sheets

ملف واحد بأربع تبويبات: `Daily_Log`, `Current_Plan`, `Plan_History`, `System_Control`
(راجع `lib/config.py` للأعمدة بالضبط).

`System_Control!B1` يجب أن تحتوي `active` أو `paused` — أي سكربت يتحقق منها أولاً
ويتوقف فوراً لو كانت `paused` (زر إيقاف طارئ).

## الأمان

- كل الأسرار من متغيرات البيئة فقط، لا شي مكتوب بالكود
- `.env` مضاف لـ`.gitignore` ولن يُرفع أبداً
- أخطاء غير متوقعة تُقترح لها إصلاحات عبر Pull Request فقط — لا دمج تلقائي أبداً
