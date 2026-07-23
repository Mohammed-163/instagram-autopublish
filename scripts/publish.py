```python
# الحصول على رؤوس الأعمدة المتاحة في الشيت لتفادي خطأ العمود المفقود
headers = sheets.get_headers("Daily_Log")
header_map = {str(h).lower().strip().replace(" ", "_"): h for h in headers}

# البيانات المراد تحديثها
update_fields = {
    "status": "published",
    "published_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "media_id": media_id,
    "error": ""
}

# تصفية وتطابق الحقول المفاتيح مع أسماء الأعمدة الفعلية الموجودة في Sheet
safe_fields = {}
for key, value in update_fields.items():
    if key in headers:
        safe_fields[key] = value
    elif key in header_map:
        safe_fields[header_map[key]] = value

# إجراء التحديث فقط للحقول المقبولة والموجودة في جدول البيانات
if safe_fields:
    sheets.update_row_fields(
        tab_name="Daily_Log",
        row_index=row_index,
        fields=safe_fields
    )
```