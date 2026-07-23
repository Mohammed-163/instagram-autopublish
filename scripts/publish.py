```python
# تحديث بيانات الصف في Daily_Log مع مطابقة مسميات الأعمدة المتوقعة
try:
    headers = sheets.get_headers("Daily_Log")
except AttributeError:
    headers = []

# تحديد الاسم الصحيح لعمود المعرف المتاح في الشيت (Media ID أو Instagram Media ID أو غيرها)
media_id_key = "Media ID"
if headers:
    for candidate in ["Media ID", "Instagram Media ID", "Post ID", "IG Media ID"]:
        if candidate in headers:
            media_id_key = candidate
            break

payload = {
    "Status": "Published",
    media_id_key: media_id,
    "Instagram Link": post_url if 'post_url' in locals() else instagram_url,
    "Error": ""
}

# تصفية الحقول لضمان إرسال الأعمدة الموجودة فقط في هيدر الشيت
if headers:
    fields_to_update = {k: v for k, v in payload.items() if k in headers}
else:
    fields_to_update = payload

sheets.update_row_fields(
    tab_name="Daily_Log",
    row_index=row_index if 'row_index' in locals() else row_num,
    fields=fields_to_update
)
```