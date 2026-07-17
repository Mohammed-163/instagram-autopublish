# تقرير الإعداد — الأسرار المطلوبة كاملة

> أنشئ كل سر عبر: **Settings → Secrets and variables → Actions → New repository secret**

هذي كل الأسرار اللي تستخدمها الـ5 workflows فعلياً (استخرجتها آلياً من ملفات `.yml` نفسها، مو من الذاكرة، فهي مطابقة 100% لواقع الكود).

## 1) عندك بالفعل (من الصورة اللي أرسلتها)

| السر | الاستخدام |
|---|---|
| `GOOGLE_DRIVE_FOLDER_ID` | مجلد Drive الجذر لتخزين الفيديوهات المؤقتة |
| `GOOGLE_SERVICE_ACCOUNT_JSON_B64` | Service Account — **لـGoogle Sheets فقط** (Base64 لملف JSON الأصلي) |
| `IG_ACCESS_TOKEN` | توكن Instagram Graph API طويل الأمد |
| `IG_BUSINESS_ID` | معرّف حساب انستغرام Business |

## 2) لازم تتأكد إنك أضفتها (ذكرتها بردك الأخير أنك فصلتها)

| السر | الاستخدام |
|---|---|
| `GOOGLE_OAUTH_TOKEN_JSON_B64` | محتوى `token.json` بصيغة OAuth — **لـGoogle Drive فقط**. لا تخلطه أبداً بسر Sheets أعلاه، الصيغتان مختلفتان تماماً |

## 3) ناقصة عندك — لازم تضيفها الآن قبل أي تشغيل فعلي

| السر | الاستخدام | من وين تجيبه |
|---|---|---|
| `GOOGLE_SHEET_ID` | معرّف ملف Google Sheets (`Content_System`) | من رابط الشيت نفسه: `docs.google.com/spreadsheets/d/{SHEET_ID}/edit` |
| `GEMINI_API_KEY_1` | مفتاح Gemini API الأول (توليد المحتوى، الخطة الشهرية، تشخيص الأخطاء) | Google AI Studio |
| `GEMINI_API_KEY_2` | مفتاح احتياطي عند انتهاء حصة المفتاح الأول | Google AI Studio (حساب/مشروع ثاني إن أمكن، لحصة منفصلة فعلاً) |
| `GEMINI_API_KEY_3` | مفتاح احتياطي ثالث | نفس الفكرة |
| `PIXABAY_API_KEY` | تحميل خلفيات الفيديو | Pixabay → حسابك → API docs |
| `TELEGRAM_BOT_TOKEN` | إرسال تنبيهات النظام | من BotFather بتلغرام |
| `TELEGRAM_CHAT_ID` | رقم المحادثة/القناة اللي تستقبل التنبيهات | أرسل أي رسالة للبوت، ثم افتح `api.telegram.org/bot<TOKEN>/getUpdates` وشوف `chat.id` |
| `FB_APP_ID` | تجديد توكن Instagram شهرياً (`fb_exchange_token`) | Meta for Developers → إعدادات التطبيق |
| `FB_APP_SECRET` | نفس الغرض أعلاه | Meta for Developers → إعدادات التطبيق |
| `GH_PAT` | Personal Access Token بصلاحية `repo` — يُستخدم لتحديث سر `IG_ACCESS_TOKEN` تلقائياً شهرياً، إنشاء فروع/PR لإصلاحات Gemini، والتزام (commit) ملفات النسخ الاحتياطي الأسبوعي | GitHub → Settings → Developer settings → Personal access tokens (classic كافي، صلاحية `repo` فقط) |

`GH_REPO` **مو سر** — يُبنى تلقائياً من `${{ github.repository }}` بكل الـworkflows، ما تحتاج تضيفه يدوياً.

## 4) ملاحظة أمنية على `GH_PAT`

هذا التوكن يقدر يكتب بالريبو (فتح فروع، PR، تحديث أسرار أخرى، commit ملفات). أنشئه بأضيق صلاحية ممكنة (`repo` فقط، مو `admin` أو صلاحيات تنظيمية)، ولو الريبو تحت حساب شخصي وليس منظمة، هذا يكفي تماماً.

## 5) الترتيب المقترح للاختبار بعد إضافة الناقص

1. شغّل `Test - Drive to Instagram Validation` يدوياً (Actions → اختره → Run workflow) — يتحقق فقط من `GOOGLE_OAUTH_TOKEN_JSON_B64` + `GOOGLE_DRIVE_FOLDER_ID` + `IG_ACCESS_TOKEN` + `IG_BUSINESS_ID`، ما يحتاج باقي الأسرار
2. بعد نجاحه، شغّل `Daily Generate` يدوياً (`workflow_dispatch`) — يتحقق من Sheets + Gemini + Pixabay بالإضافة لما سبق
3. راجع Google Sheets يدوياً وتأكد إن صف جديد انكتب بـ`Daily_Log` بحالة `ready`
4. شغّل `Publish` يدوياً وتأكد إنه نشر ذاك الصف فعلياً وغيّر حالته لـ`published`
5. شغّل `Cleanup` يدوياً وتأكد إنه حذف الفيديو من Drive وغيّر الحالة لـ`cleaned`
6. **فقط بعد نجاح كل هذا يدوياً**: افتح كل ملف `.yml`، احذف `#` من أسطر `cron` بالأعلى (تحت `on:`)، وارفع التعديل — هذا يفعّل الجدولة التلقائية الحقيقية

لا تفعّل الجدولة التلقائية قبل اجتياز الخطوات 1-5 يدوياً كلها — لأن أي خطأ بعدها ينشر محتوى حقيقي بدون رقابة.
