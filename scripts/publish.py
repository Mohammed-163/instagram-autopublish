```python
# جلب الترويسات (Headers) المتاحة للتحقق من وجود العمود قبل تحديثه
try:
    headers = sheets.get_headers("Daily_Log")
except AttributeError:
    headers = []

# إعداد الحقول الأساسية المراد تحديثها
fields_to_update = {
    "status": "published",
    "published_at": datetime.now().isoformat()
}

# البحث عن الاسم المطابق لعمود معرّف المنشور إن وجد في الجدول
media_col = next((col for col in ["media_id", "post_id", "ig_id", "id"] if col in headers), None)
if media_col:
    fields_to_update[media_col] = media_id

# تصفية الحقول لتشمل فقط الحقول الموجودة بالفعل في الترويسة
if headers:
    fields_to_update = {k: v for k, v in fields_to_update.items() if k in headers}

# تحديث السطر بالحقول المتوافقة فقط
sheets.update_row_fields(
    tab_name="Daily_Log",
    row_index=row_index,
    fields=fields_to_update
)
```